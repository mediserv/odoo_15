# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from odoo import models, fields, api
from odoo.tools.misc import formatLang, format_date, get_lang
from odoo.tools.translate import _
from odoo.tools import append_content_to_html, DEFAULT_SERVER_DATE_FORMAT, html2plaintext
from odoo.exceptions import UserError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class AcountFollowupReport(models.AbstractModel):
    _inherit = "account.followup.report"
    
    
    def _get_columns_name(self, options):
        """
        Override
        Return the name of the columns of the follow-ups report
        """
        headers = [{'name': _('#'), 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Coverage Period'), 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Due Date'), 'class': 'date', 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Contributions Due'), 'class': 'number o_price_total', 'style': 'text-align:center; white-space:normal;'},
                   {'name': _('Fixed Charges'), 'class': 'number o_price_total', 'style': 'text-align:center; white-space:normal;'},
                   {'name': _('Cumulative Penalties'), 'class': 'number o_price_total', 'style': 'text-align:center; white-space:normal;'},
                   {'name': _('Charges after Day 90'), 'class': 'number o_price_total', 'style': 'text-align:center; white-space:normal;'},
                   {'name': _('Penalties & Charges'), 'class': 'number o_price_total', 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Debt Due'), 'class': 'number o_price_total', 'style': 'text-align:center; white-space:nowrap;'}
                  ]
               
        if self.env.context.get('print_mode'):
            headers = headers[:]  # Remove the 'Expected Date' and 'Excluded' columns
        return headers

    def _get_lines(self, options, line_id=None):
        """
        Override
        Compute and return the lines of the columns of the follow-ups report.
        """
        # Get date format for the lang
        partner = options.get('partner_id') and self.env['res.partner'].browse(options['partner_id']) or False

        if not partner:
            return []

        lang_code = partner.lang if self._context.get('print_mode') else self.env.user.lang or get_lang(self.env).code
        lines = []
        res = {}
        today = fields.Date.today()
        line_num = 0
        is_payment_count =0
        invoice_count = 0
        risk_reserve_one = False
        for item in partner.category_id:
            if item.id == 2:
                risk_reserve_one = True
        for l in partner.unreconciled_aml_ids.filtered(lambda l: l.company_id == self.env.company):
            if l.company_id == self.env.company:
                if self.env.context.get('print_mode') and l.blocked:
                    continue
                currency = l.currency_id or l.company_id.currency_id
                if currency not in res:
                    res[currency] = []
                res[currency].append(l)
        for currency, aml_recs in res.items():
            total = 0
            total_issued = 0
            grand_total_penalties = 0
            gross_debt_due = 0
            aml_recs.sort(key=lambda y: (y.amount_residual <=0, y.date_maturity or y.date))
            overdue_count = 0 if risk_reserve_one else 1
            for aml in aml_recs:
                amount = aml.amount_residual_currency if aml.currency_id else aml.amount_residual
                date_due = format_date(self.env, aml.date_maturity or aml.date, lang_code=lang_code)
                date_due_num = aml.date_maturity or aml.date
                total += not aml.blocked and amount or 0
                is_overdue = today > aml.date_maturity if aml.date_maturity else today > aml.date
                is_payment = aml.payment_id 
                if is_payment and aml.suspended_payment == True:
                      Coverage_Start = "Contribution is in Suspense"
                      Coverage_Start = {'name': Coverage_Start,  'style': 'white-space:nowrap;text-align:center;color: red;'}
                elif  is_payment or amount < 0:
                    date_due =  format_date(self.env, aml.date, lang_code=lang_code)
                    Coverage_Start = "Contribution is not Applied"
                else:
                    Coverage_Start = format_date(self.env, aml.move_id.x_Coverage_StartDate, lang_code=lang_code) + " – " + format_date(self.env, aml.move_id.x_Coverage_Enddate, lang_code=lang_code)
                if is_overdue or is_payment:
                    total_issued += not aml.blocked and amount or 0
                if is_overdue and amount >0:
                    overdue_count += 1
                    if overdue_count <=4:
                        date_due = {'name': date_due, 'class': 'color-orange date', 'style': 'white-space:nowrap;text-align:center;color: orange;'}
                if is_overdue and amount >0 and overdue_count >4:
                    date_due = {'name': date_due, 'class': 'color-red date', 'style': 'white-space:nowrap;text-align:center;color: red;'}
                if amount >0 and overdue_count >4:
                    Coverage_Start = {'name': Coverage_Start,  'style': 'white-space:nowrap;text-align:center;color: red;'}
    
                overdue_days = (today - date_due_num).days
                fixed_charges = 1000 if overdue_days >= 90 else 500 if overdue_days >= 60 else 200 if overdue_days >= 30 else 0
                fixed_charges_st = formatLang(self.env, fixed_charges, currency_obj=currency) if fixed_charges > 0 else '–'
                if amount >= 0:
                    cumulative_penalties = ((((((amount + 200) * 1.05) + 300) *1.10) + 500) * .15) + (((((amount + 200) * 1.05) + 300) *.10) + ((amount + 200) * .05)) if overdue_days >= 90 else ((((amount + 200) * 1.05) + 300) *.10) + ((amount + 200) * .05) if overdue_days >= 60 else ((amount + 200) * .05) if overdue_days >= 30 else 0
                else:
                    cumulative_penalties = 0
                cumulative_penalties_st = formatLang(self.env, cumulative_penalties, currency_obj=currency) if cumulative_penalties > 0 else '–'
                monthcount = (today.year  - (date_due_num+ relativedelta(days=90)).year) * 12 + (today.month - (date_due_num + relativedelta(days=90)).month)
                daysafter_ninty_day= (today - (date_due_num + relativedelta(days=90))).days
                ninty_day_charge = ((amount + cumulative_penalties) * .025) if daysafter_ninty_day > 0 and monthcount == 0 else (monthcount + 1) * ((amount + cumulative_penalties) * .025) if monthcount > 0 else 0
                ninty_day_charge_st = formatLang(self.env, ninty_day_charge, currency_obj=currency) if ninty_day_charge > 0 else '–'
                total_penalties = ninty_day_charge + cumulative_penalties + fixed_charges if cumulative_penalties >0 or ninty_day_charge >0 else 0
                total_penalties_st = formatLang(self.env, total_penalties, currency_obj=currency) if total_penalties > 0 else '–'
                gross_debt = total_penalties + amount
                gross_debt_st = formatLang(self.env, gross_debt, currency_obj=currency)
                grand_total_penalties += not aml.blocked and total_penalties or 0
                gross_debt_due += not aml.blocked and gross_debt or 0

                
                cumulative_penalties_st = {'name': cumulative_penalties_st,  'style': 'white-space:nowrap;text-align:right;'}
                ninty_day_charge_st = {'name': ninty_day_charge_st,  'style': 'white-space:nowrap;text-align:right;'}
                total_penalties_st = {'name': total_penalties_st,  'style': 'white-space:nowrap;text-align:right;'}
                gross_debt_st = {'name': gross_debt_st,  'style': 'white-space:nowrap;text-align:right;'}
                line_num += 1
                invoice_count = line_num
                if is_payment or amount < 0 :
                    fixed_charges_st = '–'
                    is_payment_count += 1
                    invoice_count = is_payment_count
                fixed_charges_st = {'name': fixed_charges_st,  'style': 'white-space:nowrap;text-align:right;'}
               
                
                
                move_line_name = self._format_aml_name(aml.name, aml.move_id.ref, aml.move_id.name)
                if self.env.context.get('print_mode'):
                    move_line_name = {'name': move_line_name, 'style': 'text-align:right; white-space:normal;'}
                amount = formatLang(self.env, amount, currency_obj=currency)
                amount_st = amount
                amount_st = {'name': amount_st,  'style': 'white-space:nowrap;text-align:right;'}
                expected_pay_date = format_date(self.env, aml.expected_pay_date, lang_code=lang_code) if aml.expected_pay_date else ''
                invoice_origin = aml.move_id.invoice_origin or ''
                if len(invoice_origin) > 43:
                    invoice_origin = invoice_origin[:40] + '...'
                columns = [
                    Coverage_Start,
                    date_due,
                    amount_st,
                    fixed_charges_st,
                    cumulative_penalties_st,
                    ninty_day_charge_st,
                    total_penalties_st,
                    gross_debt_st,
                    
                ]
                if self.env.context.get('print_mode'):
                    columns = columns[:]
                lines.append({
                    'id': aml.id,
                    'account_move': aml.move_id,
                    'name': invoice_count,
                    'caret_options': 'followup',
                    'move_id': aml.move_id.id,
                    'type': is_payment and 'payment' or 'unreconciled_aml',
                    'unfoldable': False,
                    'columns': [type(v) == dict and v or {'name': v} for v in columns],
                })
            total_due = formatLang(self.env, total, currency_obj=currency)
            line_num += 1
            lines.append({
                'id': line_num,
                'name': '',
                'class': 'total',
                'style': 'border-top-style: double',
                'unfoldable': False,
                'level': 3,
                'columns': [{'name': v} for v in [''] * (6 if self.env.context.get('print_mode') else 6) + [total >= 0 and _('Total Due') or '', total_due]],
            })
            if total_issued > 0:
                total_issued = formatLang(self.env, total_issued, currency_obj=currency)
                line_num += 1
                lines.append({
                    'id': line_num,
                    'name': '',
                    'class': 'total',
                    'unfoldable': False,
                    'level': 3,
                    'columns': [{'name': v} for v in [''] * (6 if self.env.context.get('print_mode') else 6) + [_('Total Overdue'), total_issued]],
                })
            if grand_total_penalties > 0:
                grand_total_penalties = formatLang(self.env, grand_total_penalties, currency_obj=currency)
                line_num += 1
                lines.append({
                    'id': line_num,
                    'name': '',
                    'class': 'total',
                    'unfoldable': False,
                    'level': 3,
                    'columns': [{'name': v} for v in [''] * (6 if self.env.context.get('print_mode') else 6) + [_('Total Penalties & Charges'), grand_total_penalties]],
                })
            if gross_debt_due > 0:
                gross_debt_due = formatLang(self.env, gross_debt_due, currency_obj=currency)
                line_num += 1
                lines.append({
                    'id': line_num,
                    'name': '',
                    'class': 'total',
                    'unfoldable': False,
                    'level': 3,
                    'columns': [{'name': v} for v in [''] * (6 if self.env.context.get('print_mode') else 6) + [_('Goss Debt Due'), gross_debt_due]],
                })
            
            
            # Add an empty line after the total to make a space between two currencies
            line_num += 1
            lines.append({
                'id': line_num,
                'name': '',
                'class': '',
                'style': 'border-bottom-style: none',
                'unfoldable': False,
                'level': 0,
                'columns': [{} for col in columns],
            })
        # Remove the last empty line
        if lines:
            lines.pop()
        return lines
