import base64
import io

import xlsxwriter

from odoo import models


class ProjectEstimateXlsx(models.Model):
    _inherit = 'construction.project.estimate'

    def action_print_bq_xlsx(self):
        """Build an XLSX file mirroring the BQ Summary report and return a
        download action."""
        self.ensure_one()
        bq = self.get_bq_summary()

        buffer = io.BytesIO()
        wb = xlsxwriter.Workbook(buffer, {'in_memory': True})
        ws = wb.add_worksheet('BQ')

        title_fmt = wb.add_format({
            'bold': True, 'font_size': 14, 'align': 'center',
        })
        header_fmt = wb.add_format({
            'bold': True, 'bg_color': '#D9E1F2', 'border': 1,
            'align': 'center', 'valign': 'vcenter',
        })
        section_fmt = wb.add_format({
            'bold': True, 'bg_color': '#BDD7EE', 'border': 1,
        })
        cell_fmt = wb.add_format({'border': 1})
        center_fmt = wb.add_format({'border': 1, 'align': 'center'})
        num_fmt = wb.add_format({'border': 1, 'num_format': '#,##0.00'})
        total_fmt = wb.add_format({
            'bold': True, 'border': 1, 'bg_color': '#FFF2CC',
            'num_format': '#,##0.00',
        })
        total_lbl_fmt = wb.add_format({
            'bold': True, 'border': 1, 'bg_color': '#FFF2CC',
            'align': 'right',
        })
        grand_fmt = wb.add_format({
            'bold': True, 'border': 1, 'bg_color': '#F4B084',
            'num_format': '#,##0.00',
        })
        grand_lbl_fmt = wb.add_format({
            'bold': True, 'border': 1, 'bg_color': '#F4B084',
            'align': 'right',
        })
        meta_lbl_fmt = wb.add_format({'bold': True})

        ws.set_column('A:A', 5)
        ws.set_column('B:B', 40)
        ws.set_column('C:C', 12)
        ws.set_column('D:D', 8)
        ws.set_column('E:E', 14)
        ws.set_column('F:F', 8)
        ws.set_column('G:G', 16)

        ws.merge_range('A1:G1', 'Bill Of Quantity', title_fmt)
        ws.write('A3', 'Estimate:', meta_lbl_fmt)
        ws.write('B3', self.name or '')
        ws.write('A4', 'Customer:', meta_lbl_fmt)
        ws.write('B4', self.customer_id.name or '')
        ws.write('A5', 'Date:', meta_lbl_fmt)
        ws.write('B5', self.date and str(self.date) or '')

        row = 7
        headers = ['No', 'Particular', 'Quantity', 'Unit',
                   'Rate', 'Per', 'Amount']
        for col, h in enumerate(headers):
            ws.write(row, col, h, header_fmt)
        row += 1

        ws.merge_range(row, 0, row, 6, 'Material', section_fmt)
        row += 1
        for idx, r in enumerate(bq['materials'], 1):
            ws.write(row, 0, idx, center_fmt)
            ws.write(row, 1, r['name'], cell_fmt)
            ws.write_number(row, 2, r['total_qty'], num_fmt)
            ws.write(row, 3, r['uom'], center_fmt)
            ws.write_number(row, 4, r['rate'], num_fmt)
            ws.write_number(row, 5, r['per'], num_fmt)
            ws.write_number(row, 6, r['total_amount'], num_fmt)
            row += 1
        ws.merge_range(row, 0, row, 5, 'Total Cost of Materials',
                       total_lbl_fmt)
        ws.write_number(row, 6, bq['material_subtotal'], total_fmt)
        row += 2

        ws.merge_range(row, 0, row, 6, 'Labour', section_fmt)
        row += 1
        for idx, r in enumerate(bq['labours'], 1):
            ws.write(row, 0, idx, center_fmt)
            ws.write(row, 1, r['name'], cell_fmt)
            ws.write_number(row, 2, r['total_qty'], num_fmt)
            ws.write(row, 3, r['uom'], center_fmt)
            ws.write_number(row, 4, r['rate'], num_fmt)
            ws.write_number(row, 5, r['per'], num_fmt)
            ws.write_number(row, 6, r['total_amount'], num_fmt)
            row += 1
        ws.merge_range(row, 0, row, 5, 'Total Cost of Labours',
                       total_lbl_fmt)
        ws.write_number(row, 6, bq['labour_subtotal'], total_fmt)
        row += 2

        ws.merge_range(row, 0, row, 5, 'Grand Total (Mat + Lab)',
                       grand_lbl_fmt)
        ws.write_number(row, 6, bq['grand_total'], grand_fmt)

        wb.close()
        buffer.seek(0)
        safe_name = (self.name or 'BQ').replace('/', '_').replace('\\', '_')
        filename = f'BQ - {safe_name}.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(buffer.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': (
                'application/vnd.openxmlformats-officedocument.'
                'spreadsheetml.sheet'
            ),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
