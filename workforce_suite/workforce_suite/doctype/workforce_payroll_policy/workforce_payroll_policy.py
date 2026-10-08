from frappe import _
from frappe.model.document import Document


class WorkforcePayrollPolicy(Document):
    def validate(self):
        if self.standard_hours_per_day <= 0:
            raise ValueError(_("Standard hours per day must be greater than zero"))
        if self.break_minutes < 0:
            raise ValueError(_("Break minutes cannot be negative"))
        if self.pay_basis == "Daily Wage" and self.daily_wage <= 0:
            raise ValueError(_("Daily wage must be greater than zero for a daily-wage policy"))
        if self.overtime_enabled:
            if self.overtime_after_hours <= 0:
                raise ValueError(_("Overtime after hours must be greater than zero"))
            if self.overtime_grace_minutes < 0:
                raise ValueError(_("Overtime grace minutes cannot be negative"))
            if self.overtime_rounding_minutes <= 0:
                raise ValueError(_("Overtime rounding minutes must be greater than zero"))
            if self.overtime_multiplier not in (1, 2):
                raise ValueError(_("Overtime multiplier must be 1 or 2"))
            if self.max_daily_overtime_hours < 0 or self.max_weekly_hours <= 0:
                raise ValueError(_("Overtime limits must be valid non-negative values"))
