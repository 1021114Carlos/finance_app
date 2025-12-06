from dataclasses import dataclass
from fasthtml.common import *

# Create app, serve static, link external CSS 
app, rt = fast_app(
    static_dir="static",
    hdrs=(Link(rel="stylesheet", href="/static/styles.css"),)
)

# Data model 
@dataclass
class FinanceInput:
    housing_status: str
    housing_payment: float
    auto_payment: float
    credit_payment: float
    student_payment: float
    monthly_after_tax_income: float   # per paycheck (biweekly)
    save_percent: float               # percent of leftover to save
    period_mode: str = "paycheck"     # "paycheck" or "monthly"
    show_annual: str = ""             # checkbox; non-empty if checked


#  Validation 
def validate(finance: FinanceInput):
    errors = []
    if finance.housing_payment < 0:
        errors.append("Housing payment cannot be negative.")
    if finance.auto_payment < 0:
        errors.append("Auto loan payment cannot be negative.")
    if finance.credit_payment < 0:
        errors.append("Credit card payment cannot be negative.")
    if finance.student_payment < 0:
        errors.append("Student loan payment cannot be negative.")
    if finance.monthly_after_tax_income < 0:
        errors.append("Take-home pay per paycheck cannot be negative.")
    if finance.save_percent < 0 or finance.save_percent > 100:
        errors.append("Percent to save must be between 0 and 100.")
    return errors


# Recommended biweekly logic 
def analyze_finance(data: FinanceInput):
    total_debt = (
        data.housing_payment
        + data.auto_payment
        + data.credit_payment
        + data.student_payment
    )

    income = data.monthly_after_tax_income
    available_cash = income - total_debt

    if available_cash <= 0:
        can_save = False
        savings = 0.0
        spending = available_cash
    else:
        can_save = True
        save_fraction = max(0.0, min(data.save_percent, 100.0)) / 100.0
        savings = available_cash * save_fraction
        spending = available_cash - savings

    # Ratios and projections
    debt_income_ratio = None
    if income > 0:
        debt_income_ratio = total_debt / income

    paychecks_per_year = 26
    monthly_factor = paychecks_per_year / 12.0  # ~2.1667

    # Monthly equivalents (approximate)
    total_debt_monthly = total_debt * monthly_factor
    available_monthly = available_cash * monthly_factor
    monthly_savings = savings * monthly_factor
    monthly_spending = spending * monthly_factor

    # Annual projections
    annual_savings = savings * paychecks_per_year
    annual_spending = spending * paychecks_per_year

    fmt = lambda x: f"{round(x, 2):.2f}"

    return {
        # per-paycheck
        "total_debt": fmt(total_debt),
        "available_cash": fmt(available_cash),
        "savings_per_paycheck": fmt(savings),
        "spending_per_paycheck": fmt(spending),

        # monthly equivalents
        "total_debt_monthly": fmt(total_debt_monthly),
        "available_monthly": fmt(available_monthly),
        "monthly_savings": fmt(monthly_savings),
        "monthly_spending": fmt(monthly_spending),

        # annual
        "annual_savings": fmt(annual_savings),
        "annual_spending": fmt(annual_spending),

        # raw values for logic/advice/chart
        "can_save": can_save,
        "available_cash_raw": available_cash,
        "total_debt_raw": total_debt,
        "income_raw": income,
        "debt_income_ratio": debt_income_ratio,
        "savings_raw": savings,
        "spending_raw": spending,
    }


# Advice generation 
def advice_messages(result: dict):
    msgs = []

    available = result["available_cash_raw"]
    total_debt = result["total_debt_raw"]
    income = result["income_raw"]
    r = result["debt_income_ratio"]

    if available < 0:
        msgs.append(
            "You are short this period. First goal: get leftover cash to at least 0. "
            "Options: reduce non-essential spending, pause extra debt payments, or temporarily increase income "
            "(overtime, side work, selling unused items)."
        )
        msgs.append(
            "List your must-pay bills vs. flexible expenses. Anything flexible should be cut or reduced "
            "until leftover cash is non-negative."
        )

    if r is not None:
        if r > 0.6:
            msgs.append(
                "Your debt payments are more than 60% of your income this period. This is very heavy. "
                "Consider refinancing, consolidating, or focusing on paying down one high-interest debt while "
                "keeping others at minimum payments."
            )
        elif r > 0.4:
            msgs.append(
                "Your debt payments are between 40% and 60% of your income this period. This is high. "
                "Be careful taking on new debt and try to reduce one balance consistently."
            )

    savings_raw = result["savings_raw"]
    if available > 0 and savings_raw < max(20, 0.05 * available):
        msgs.append(
            "You have leftover cash but are saving a small portion of it. "
            "If possible, slowly increase your save percentage (for example, +1% every month) "
            "until you reach a level that feels sustainable."
        )

    return msgs


#  Simple horizontal bar chart (per-paycheck) 
def bar_chart(result: dict):
    debt = max(result["total_debt_raw"], 0)
    savings = max(result["savings_raw"], 0)
    spending = max(result["spending_raw"], 0)

    total = debt + savings + max(spending, 0)
    if total <= 0:
        return Div(
            P("No positive amounts to display in the chart.", cls="muted"),
            cls="chart"
        )

    def pct(x):
        return round(100 * x / total, 1)

    rows = []
    for label, value in [
        ("Debt", debt),
        ("Savings", savings),
        ("Spending", max(spending, 0)),
    ]:
        width = 0 if value <= 0 else pct(value)
        rows.append(
            Div(
                Span(label, cls="chart-label"),
                Div(
                    Div(cls="chart-bar", style=f"width: {width}%;"),
                    cls="chart-bar-wrapper",
                ),
                Span(f"{width:.1f}%", cls="muted"),
                cls="chart-row",
            )
        )

    return Div(
        H3("Per-paycheck breakdown (percentage of income)"),
        *rows,
        P("Chart is based on per-paycheck values; percentages are the same for monthly.", cls="muted"),
        cls="chart card",
    )


# ---------- GET route ----------
@rt("/")
def get():
    return Titled(
        "Finance Calculator – Paycheck / Monthly Toggle",
        Main(
            P(
                "Enter your typical biweekly paycheck. All amounts are PER PAYCHECK. "
                "You can view results per paycheck or in monthly equivalents using the toggle. "
                "Values are rounded to two decimals without currency symbols or commas."
            ),
            Form(
                # HOUSING
                Fieldset(
                    Legend("Housing"),
                    Label("Housing status"),
                    Select(
                        Option("Rent", value="rent"),
                        Option("Own", value="own"),
                        name="housing_status",
                    ),
                    Label("Housing payment (per paycheck)"),
                    Input(
                        type="number",
                        name="housing_payment",
                        step="0.01",
                        value="0",
                        min="0",
                        required=True,
                    ),
                ),

                # DEBTS
                Fieldset(
                    Legend("Debt payments (per paycheck)"),
                    Div(
                        Div(
                            Label("Auto loan payment"),
                            Input(
                                type="number",
                                name="auto_payment",
                                step="0.01",
                                value="0",
                                min="0",
                                required=True,
                            ),
                        ),
                        Div(
                            Label("Credit card payment"),
                            Input(
                                type="number",
                                name="credit_payment",
                                step="0.01",
                                value="0",
                                min="0",
                                required=True,
                            ),
                        ),
                        Div(
                            Label("Student loan payment"),
                            Input(
                                type="number",
                                name="student_payment",
                                step="0.01",
                                value="0",
                                min="0",
                                required=True,
                            ),
                        ),
                        cls="grid",
                    ),
                ),

                # INCOME + SAVINGS
                Fieldset(
                    Legend("Income and savings"),
                    Label("Take-home pay per paycheck (after tax)"),
                    Input(
                        type="number",
                        name="monthly_after_tax_income",
                        step="0.01",
                        value="0",
                        min="0",
                        required=True,
                    ),
                    Label("Percentage of leftover cash to save"),
                    Input(
                        type="number",
                        name="save_percent",
                        step="0.01",
                        value="10",
                        min="0",
                        max="100",
                        required=True,
                    ),
                    P(
                        "Example: if you have 500.00 left after debts and choose 20, "
                        "you'll save 100.00 and keep 400.00 in that paycheck.",
                        cls="muted",
                    ),
                ),

                # VIEW MODE TOGGLE
                Fieldset(
                    Legend("View mode"),
                    Label(
                        Input(
                            type="radio",
                            name="period_mode",
                            value="paycheck",
                            checked=True,
                        ),
                        " Per paycheck (biweekly)",
                    ),
                    Label(
                        Input(
                            type="radio",
                            name="period_mode",
                            value="monthly",
                        ),
                        " Per month (approximate, based on 26 paychecks per year ÷ 12)",
                    ),
                ),

                # EXTRA VIEWS
                Fieldset(
                    Legend("Extra views"),
                    Label(
                        Input(
                            type="checkbox",
                            name="show_annual",
                        ),
                        " Show annual projection (26 paychecks per year).",
                    ),
                ),

                Button("Calculate", type="submit"),
                hx_post="/analyze",
                hx_target="#result",
                hx_swap="innerHTML",
            ),
            Div(id="result"),
        ),
    )


# ---------- POST route ----------
@rt("/analyze")
def post(finance: FinanceInput):
    errors = validate(finance)
    if errors:
        return Div(
            Article(
                H2("Please correct the following issues:"),
                Ul(*(Li(e) for e in errors)),
                cls="card",
            ),
            id="result",
        )

    result = analyze_finance(finance)
    mode = finance.period_mode or "paycheck"
    show_annual = bool(finance.show_annual)

    # Summary text depends on mode
    if result["available_cash_raw"] <= 0:
        if mode == "monthly":
            summary = (
                "You do not have leftover cash after debts (in the monthly equivalent). "
                "You cannot save based on these numbers."
            )
        else:
            summary = (
                "You do not have leftover cash after debts this paycheck. "
                "You cannot save based on these numbers."
            )
        summary_cls = "result-bad"
    else:
        if mode == "monthly":
            summary = (
                f"Monthly equivalent: you have {result['available_monthly']} left after debts. "
                f"You save {result['monthly_savings']} and keep "
                f"{result['monthly_spending']} for other expenses per month."
            )
        else:
            summary = (
                f"You have {result['available_cash']} left after debts this paycheck. "
                f"You save {result['savings_per_paycheck']} and keep "
                f"{result['spending_per_paycheck']} for other expenses."
            )
        summary_cls = "result-good"

    # Main details list
    items = []
    if mode == "monthly":
        items.extend([
            Li(f"total_debt_per_month (approx): {result['total_debt_monthly']}"),
            Li(f"available_cash_before_saving_per_month (approx): {result['available_monthly']}"),
            Li(f"savings_per_month (approx): {result['monthly_savings']}"),
            Li(f"spending_money_per_month (approx): {result['monthly_spending']}"),
        ])
    else:
        items.extend([
            Li(f"total_debt_per_paycheck: {result['total_debt']}"),
            Li(f"available_cash_before_saving: {result['available_cash']}"),
            Li(f"savings_per_paycheck: {result['savings_per_paycheck']}"),
            Li(f"spending_money_per_paycheck: {result['spending_per_paycheck']}"),
        ])

    if show_annual:
        items.append(
            Li(
                f"annual_savings (26 paychecks): {result['annual_savings']} "
                f"| annual_spending (26 paychecks): {result['annual_spending']}"
            )
        )

    # Advice
    advice = advice_messages(result)
    advice_block = None
    if advice:
        advice_block = Article(
            H3("Advice based on these numbers"),
            Ul(*(Li(msg) for msg in advice)),
            cls="card",
        )

    # Bar chart (always per-paycheck)
    chart = bar_chart(result)

    return Div(
        Article(
            H2("Results"),
            P(summary, cls=summary_cls),
            Ul(*items),
            P("If available_cash is ≤ 0, savings are set to 0.", cls="muted"),
            cls="card",
        ),
        chart,
        advice_block or "",
        id="result",
    )


# ---------- Run server ----------
serve()
