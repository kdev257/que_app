"""Default chart of accounts and system mappings (used by migrations and for future accounting)."""

# (code, name, type, group)
DEFAULT_ACCOUNTS = [
    # Assets
    ("1001", "Cash in hand", "asset", "Cash-in-hand"),
    ("1010", "Bank account", "asset", "Bank Accounts"),
    ("1020", "UPI collections", "asset", "Bank Accounts"),
    ("1030", "Card settlements receivable", "asset", "Current Assets"),
    ("1040", "Online payments receivable (Razorpay)", "asset", "Current Assets"),
    ("1100", "Stock in hand", "asset", "Stock-in-hand"),
    ("1200", "Input CGST", "asset", "Duties & Taxes"),
    ("1201", "Input SGST", "asset", "Duties & Taxes"),
    ("1202", "Input UTGST", "asset", "Duties & Taxes"),
    ("1203", "Input IGST", "asset", "Duties & Taxes"),
    ("1300", "Customers (receivable)", "asset", "Sundry Debtors"),
    # Liabilities
    ("2001", "Suppliers (payable)", "liability", "Sundry Creditors"),
    ("2100", "Output CGST", "liability", "Duties & Taxes"),
    ("2101", "Output SGST", "liability", "Duties & Taxes"),
    ("2102", "Output UTGST", "liability", "Duties & Taxes"),
    ("2103", "Output IGST", "liability", "Duties & Taxes"),
    ("2200", "QuickQueue booking fee payable", "liability", "Current Liabilities"),
    # Equity
    ("3001", "Owner's capital", "equity", "Capital Account"),
    ("3002", "Owner's drawings", "equity", "Capital Account"),
    # Income
    ("4001", "Sales - services", "income", "Sales Accounts"),
    ("4002", "Sales - food & beverages", "income", "Sales Accounts"),
    ("4900", "Other income", "income", "Indirect Incomes"),
    ("4950", "Round off", "income", "Indirect Incomes"),
    # Direct costs
    ("5001", "Purchases - stock items", "expense", "Purchase Accounts"),
    ("5002", "Cost of items used", "expense", "Direct Expenses"),
    ("5003", "Stock shortage / wastage", "expense", "Direct Expenses"),
    ("5100", "Discount allowed", "expense", "Indirect Expenses"),
    # Indirect expenses (one per default expense category)
    ("6001", "Rent", "expense", "Indirect Expenses"),
    ("6002", "Salaries & wages", "expense", "Indirect Expenses"),
    ("6003", "Electricity", "expense", "Indirect Expenses"),
    ("6004", "Water", "expense", "Indirect Expenses"),
    ("6005", "Internet & phone", "expense", "Indirect Expenses"),
    ("6006", "Repairs & maintenance", "expense", "Indirect Expenses"),
    ("6007", "Marketing & ads", "expense", "Indirect Expenses"),
    ("6008", "Bank & payment charges", "expense", "Indirect Expenses"),
    ("6009", "Professional fees (CA, legal)", "expense", "Indirect Expenses"),
    ("6010", "Licences & fees", "expense", "Indirect Expenses"),
    ("6011", "Travel & conveyance", "expense", "Indirect Expenses"),
    ("6012", "Staff food & welfare", "expense", "Indirect Expenses"),
    ("6013", "Laundry", "expense", "Indirect Expenses"),
    ("6014", "Commission paid", "expense", "Indirect Expenses"),
    ("6015", "Software & subscriptions", "expense", "Indirect Expenses"),
    ("6016", "Insurance", "expense", "Indirect Expenses"),
    ("6999", "Other expenses", "expense", "Indirect Expenses"),
]

# Expense category name -> account code (others go to 6999)
EXPENSE_CATEGORY_CODES = {name: code for code, name, _, _ in DEFAULT_ACCOUNTS if code.startswith("60")}
EXPENSE_CATEGORY_CODES["Other"] = "6999"

# System mappings: key -> (label, account code)
SYSTEM_MAPPINGS = [
    ("sales_services", "Sales of services", "4001"),
    ("sales_food", "Sales of food & beverages", "4002"),
    ("discount_allowed", "Discounts and credit notes", "5100"),
    ("output_cgst", "Output CGST (on sales)", "2100"),
    ("output_sgst", "Output SGST (on sales)", "2101"),
    ("output_utgst", "Output UTGST (on sales)", "2102"),
    ("output_igst", "Output IGST (on sales)", "2103"),
    ("input_cgst", "Input CGST (on purchases/expenses)", "1200"),
    ("input_sgst", "Input SGST (on purchases/expenses)", "1201"),
    ("input_utgst", "Input UTGST (on purchases/expenses)", "1202"),
    ("input_igst", "Input IGST (on purchases/expenses)", "1203"),
    ("booking_fee_payable", "QuickQueue booking fee collected", "2200"),
    ("pay_cash", "Payments in cash", "1001"),
    ("pay_upi", "Payments by UPI", "1020"),
    ("pay_card", "Payments by card", "1030"),
    ("pay_bank", "Payments by bank transfer", "1010"),
    ("pay_online", "Online payments (QuickQueue / Razorpay)", "1040"),
    ("pay_other", "Other payments", "1001"),
    ("customers", "Customers (unpaid bills)", "1300"),
    ("suppliers", "Suppliers (unpaid purchase bills)", "2001"),
    ("stock_in_hand", "Stock in hand (closing stock)", "1100"),
    ("purchases", "Purchases of stock items", "5001"),
    ("cost_of_items_used", "Cost of items used", "5002"),
    ("stock_shortage", "Stock shortage / extra found", "5003"),
    ("round_off", "Round off", "4950"),
]
