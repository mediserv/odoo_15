from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools.misc import formatLang, format_date, parse_date



class AccountReconciliation(models.AbstractModel):
    _inherit = 'account.reconciliation.widget'
    _description = 'Account Reconciliation widget'
    
    @api.model
    def _get_move_line_reconciliation_proposition(self, account_id, partner_id=None):
        """ Returns two lines whose amount are opposite """

        Account_move_line = self.env['account.move.line']

        ir_rules_query = Account_move_line._where_calc([])
        Account_move_line._apply_ir_rules(ir_rules_query, 'read')
        from_clause, where_clause, where_clause_params = ir_rules_query.get_sql()
        where_str = where_clause and (" WHERE %s" % where_clause) or ''

        # Get pairs
        query = """
            SELECT a.id, b.id
            FROM account_move_line a, account_move_line b,
                 account_move move_a, account_move move_b,
                 account_journal journal_a, account_journal journal_b
            WHERE a.id != b.id
            AND move_a.id = a.move_id
            AND move_a.state = 'posted'
            AND move_a.journal_id = journal_a.id
            AND move_b.id = b.move_id
            AND move_b.journal_id = journal_b.id
            AND move_b.state = 'posted'
            AND a.amount_residual = -b.amount_residual
            AND a.balance != 0.0
            AND b.balance != 0.0
            AND NOT a.reconciled
            AND NOT move_a.suspended_payment
            AND a.account_id = %s
            AND (%s IS NULL AND b.account_id = %s)
            AND (%s IS NULL AND NOT b.reconciled OR b.id = %s)
            AND (%s is NULL OR (a.partner_id = %s AND b.partner_id = %s))
            AND a.id IN (SELECT account_move_line.id FROM {0})
            AND b.id IN (SELECT account_move_line.id FROM {0})
            ORDER BY a.date desc
            LIMIT 1
            """.format(from_clause + where_str)
        move_line_id = self.env.context.get('move_line_id') or None
        params = [
            account_id,
            move_line_id, account_id,
            move_line_id, move_line_id,
            partner_id, partner_id, partner_id,
        ] + where_clause_params + where_clause_params
        self.env.cr.execute(query, params)

        pairs = self.env.cr.fetchall()

        if pairs:
            return Account_move_line.browse(pairs[0])
        return Account_move_line
    
    @api.model
    def _domain_move_lines_for_manual_reconciliation(self, account_id, partner_id=False, excluded_ids=None, search_str=''):
        """ Create domain criteria that are relevant to manual reconciliation. """
        domain = ['&', '&', '&', ('reconciled', '=', False), ('account_id', '=', account_id), ('move_id.state', '=', 'posted'), ('suspended_payment', '=', False)]
        if partner_id:
            domain = expression.AND([domain, [('partner_id', '=', partner_id)]])
        if excluded_ids:
            domain = expression.AND([[('id', 'not in', excluded_ids)], domain])
        if search_str:
            str_domain = self._get_search_domain(search_str=search_str)
            domain = expression.AND([domain, str_domain])
        # filter on account.move.line having the same company as the given account
        account = self.env['account.account'].browse(account_id)
        domain = expression.AND([domain, [('company_id', '=', account.company_id.id)]])
        return domain

    
    
    @api.model
    def _prepare_move_lines(self, move_lines, target_currency=False, target_date=False, recs_count=0):
        """ Returns move lines formatted for the manual/bank reconciliation widget
            :param move_line_ids:
            :param target_currency: currency (browse) you want the move line debit/credit converted into
            :param target_date: date to use for the monetary conversion
        """
        ret = []

        for line in move_lines:
            company_currency = line.company_id.currency_id
            line_currency = (line.currency_id and line.amount_currency) and line.currency_id or company_currency
            if line.move_id.x_Coverage_StartDate:
                coverage_period = format_date(self.env, line.move_id.x_Coverage_StartDate,) + " – " + format_date(self.env, line.move_id.x_Coverage_Enddate,)
            else:
                coverage_period = format_date(self.env, line.date_maturity)
            ret_line = {
                'id': line.id,
                'name': line.name and line.name != '/' and line.move_id.name != line.name and line.move_id.name + ': ' + line.name or line.move_id.name,
                'ref': line.move_id.ref or '',
                # For reconciliation between statement transactions and already registered payments (eg. checks)
                # NB : we don't use the 'reconciled' field because the line we're selecting is not the one that gets reconciled
                'account_id': [line.account_id.id, line.account_id.display_name],
                'is_liquidity_line': line.account_id.internal_type == 'liquidity',
                'account_code': line.account_id.code,
                'account_name': line.account_id.name,
                'account_type': line.account_id.internal_type,
                'date_maturity': coverage_period,
                'date': format_date(self.env, line.date),
                'journal_id': [line.journal_id.id, line.journal_id.display_name],
                'partner_id': line.partner_id.id,
                'partner_name': line.partner_id.name,
                'currency_id': line_currency.id,
            }

            debit = line.debit
            credit = line.credit
            amount = line.amount_residual
            amount_currency = line.amount_residual_currency

            # For already reconciled lines, don't use amount_residual(_currency)
            if line.account_id.internal_type == 'liquidity':
                amount = debit - credit
                amount_currency = line.amount_currency

            target_currency = target_currency or company_currency

            # Use case:
            # Let's assume that company currency is in USD and that we have the 3 following move lines
            #      Debit  Credit  Amount currency  Currency
            # 1)    25      0            0            NULL
            # 2)    17      0           25             EUR
            # 3)    33      0           25             YEN
            #
            # If we ask to see the information in the reconciliation widget in company currency, we want to see
            # The following information
            # 1) 25 USD (no currency information)
            # 2) 17 USD [25 EUR] (show 25 euro in currency information, in the little bill)
            # 3) 33 USD [25 YEN] (show 25 yen in currency information)
            #
            # If we ask to see the information in another currency than the company let's say EUR
            # 1) 35 EUR [25 USD]
            # 2) 25 EUR (no currency information)
            # 3) 50 EUR [25 YEN]
            # In that case, we have to convert the debit-credit to the currency we want and we show next to it
            # the value of the amount_currency or the debit-credit if no amount currency
            if target_currency == company_currency:
                if line_currency == target_currency:
                    amount = amount
                    amount_currency = ""
                    total_amount = debit - credit
                    total_amount_currency = ""
                else:
                    amount = amount
                    amount_currency = amount_currency
                    total_amount = debit - credit
                    total_amount_currency = line.amount_currency

            if target_currency != company_currency:
                if line_currency == target_currency:
                    amount = amount_currency
                    amount_currency = ""
                    total_amount = line.amount_currency
                    total_amount_currency = ""
                else:
                    amount_currency = line.currency_id and amount_currency or amount
                    company = line.account_id.company_id
                    date = target_date or line.date
                    amount = company_currency._convert(amount, target_currency, company, date)
                    total_amount = company_currency._convert((line.debit - line.credit), target_currency, company, date)
                    total_amount_currency = line.currency_id and line.amount_currency or (line.debit - line.credit)

            ret_line['recs_count'] = recs_count
            ret_line['debit'] = amount > 0 and amount or 0
            ret_line['credit'] = amount < 0 and -amount or 0
            ret_line['amount_currency'] = amount_currency
            ret_line['amount_str'] = formatLang(self.env, abs(amount), currency_obj=target_currency)
            ret_line['total_amount_str'] = formatLang(self.env, abs(total_amount), currency_obj=target_currency)
            ret_line['amount_currency_str'] = amount_currency and formatLang(self.env, abs(amount_currency), currency_obj=line_currency) or ""
            ret_line['total_amount_currency_str'] = total_amount_currency and formatLang(self.env, abs(total_amount_currency), currency_obj=line_currency) or ""
            ret.append(ret_line)
        return ret
    
    @api.model
    def _prepare_js_reconciliation_widget_move_line(self, statement_line, line, recs_count=0):
        def format_name(line):
            if (line.name or '/') == '/':
                line_name = line.move_id.name
            else:
                line_name = line.name
                if line_name != line.move_id.name:
                    line_name = '%s: %s' % (line.move_id.name, line_name)
            return line_name

        # Full amounts.
        rec_vals = statement_line._prepare_counterpart_move_line_vals({
            'balance': -line.amount_currency if line.currency_id else -line.balance,
        }, move_line=line)
        # Residual amounts.
        rec_vals_residual = statement_line._prepare_counterpart_move_line_vals({}, move_line=line)
        if rec_vals_residual['currency_id'] != statement_line.company_currency_id.id:
            currency = self.env['res.currency'].browse(rec_vals_residual['currency_id'])
            amount_currency = rec_vals_residual['debit'] - rec_vals_residual['credit']
            balance = rec_vals_residual['amount_currency']
            amount_str = formatLang(self.env, abs(balance), currency_obj=currency)
            amount_currency_str = formatLang(self.env, abs(amount_currency), currency_obj=line.company_currency_id)
            total_amount_currency_str = formatLang(self.env, abs(rec_vals['debit'] - rec_vals['credit']), currency_obj=line.company_currency_id)
            total_amount_str = formatLang(self.env, abs(rec_vals['amount_currency']), currency_obj=currency)
        else:
            balance = rec_vals_residual['debit'] - rec_vals_residual['credit']
            amount_currency = 0.0
            amount_str = formatLang(self.env, abs(balance), currency_obj=line.company_currency_id)
            amount_currency_str = ''
            total_amount_currency_str = ''
            total_amount_str = formatLang(self.env, abs(rec_vals['debit'] - rec_vals['credit']), currency_obj=line.company_currency_id)
        if line.move_id.x_Coverage_StartDate:
            coverage_period = format_date(self.env, line.move_id.x_Coverage_StartDate,) + " – " + format_date(self.env, line.move_id.x_Coverage_Enddate,)
        else:
            coverage_period = format_date(self.env, line.date_maturity)

        js_vals = {
            'id': line.id,
            'name': format_name(line),
            'ref': line.ref or '',
            'date': format_date(self.env, line.date),
            'date_maturity': coverage_period,
            'account_id': [line.account_id.id, line.account_id.display_name],
            'account_code': line.account_id.code,
            'account_name': line.account_id.name,
            'account_type': line.account_id.internal_type,
            'journal_id': [line.journal_id.id, line.journal_id.display_name],
            'partner_id': line.partner_id.id,
            'partner_name': line.partner_id.name,
            'is_liquidity_line': bool(line.payment_id),

            'currency_id': rec_vals_residual['currency_id'],
            'debit': -balance if balance < 0.0 else 0.0,
            'credit': balance if balance > 0.0 else 0.0,
            'amount_str': amount_str,
            'amount_currency': -amount_currency,
            'amount_currency_str': amount_currency_str,
            'total_amount_currency_str': total_amount_currency_str,
            'total_amount_str': total_amount_str,
            'recs_count': recs_count,
        }

        return js_vals