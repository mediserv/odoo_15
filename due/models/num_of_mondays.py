import base64

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.addons.hr_payroll.models.browsable_object import BrowsableObject, InputLine, WorkedDays, Payslips, ResultRules
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, date_utils
from odoo.tools.misc import format_date
from odoo.tools.safe_eval import safe_eval

class HrPayslip(models.Model):
  _inherit = "hr.payslip"
  def mondays_in_month(self):
    
    for payslip1 in self:
      count1 = 0
      
      for d_ord in range(payslip1.date_from.toordinal(), payslip1.date_to.toordinal()+1):
        d = date.fromordinal(d_ord)
        if (d.weekday() == 0):
          count1 += 1
     
    payslip1.x_mondays_in_month = count1
