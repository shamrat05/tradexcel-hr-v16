"""Legacy tax exception values retained for record compatibility.

Tax Policy Exceptions no longer alter Salary Slip calculations. Native HRMS
Income Tax Slabs own the tax calculation; submitted legacy exceptions are
surfaced for review by ``financial_readiness``.
"""

TAX_ACTIONS = ("Mark Tax Exempt",)
