"""
core/invoice.py
───────────────
Generates a professional PDF invoice for a booking using ReportLab.

Install:  pip install reportlab

Usage in views.py:
    from .invoice import generate_invoice_pdf
    response = generate_invoice_pdf(booking)
    return response
"""

from io import BytesIO
from datetime import date

from django.http import HttpResponse

try:
    from reportlab.lib                  import colors
    from reportlab.lib.pagesizes        import A4
    from reportlab.lib.units            import mm
    from reportlab.lib.styles          import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums           import TA_LEFT, TA_RIGHT, TA_CENTER
    from reportlab.platypus            import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether
    )
    from reportlab.pdfgen              import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ── Brand colours ──────────────────────────────────────────────
RED    = colors.HexColor('#e8192c')
DARK   = colors.HexColor('#0f0824')
BLUE   = colors.HexColor('#1a56db')
GREEN  = colors.HexColor('#00a651')
GREY   = colors.HexColor('#64748b')
LIGHT  = colors.HexColor('#f8fafc')
BORDER = colors.HexColor('#e2e8f0')
WHITE  = colors.white
BLACK  = colors.HexColor('#111827')


class NumberedCanvas(canvas.Canvas):
    """Adds page number footer to every page."""
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_footer(self, page_count):
        self.saveState()
        self.setFont('Helvetica', 7)
        self.setFillColor(GREY)
        self.drawCentredString(
            A4[0] / 2, 18 * mm,
            f'eGarage · Invoice {self._pageNumber} of {page_count} · '
            f'This is a computer-generated document. No signature required.'
        )
        # bottom red line
        self.setStrokeColor(RED)
        self.setLineWidth(1.5)
        self.line(20 * mm, 14 * mm, A4[0] - 20 * mm, 14 * mm)
        self.restoreState()


def generate_invoice_pdf(booking) -> HttpResponse:
    """
    Returns an HttpResponse with the PDF invoice attached.
    Falls back to a plain-text response if reportlab is not installed.
    """
    if not REPORTLAB_AVAILABLE:
        return HttpResponse(
            f'Invoice for booking {booking.reference}\n'
            f'Service: {booking.service.name if booking.service else "Service"}\n'
            f'Amount: ₹{booking.final_price}\n\n'
            f'Install reportlab to generate PDF invoices:\n'
            f'pip install reportlab',
            content_type='text/plain'
        )

    buffer  = BytesIO()
    doc     = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=18*mm,  bottomMargin=28*mm,
    )

    styles  = getSampleStyleSheet()
    story   = []

    # ── helpers ──────────────────────────────────────────────

    def para(text, style, **kwargs):
        merged = ParagraphStyle('_', parent=style, **kwargs)
        return Paragraph(text, merged)

    def hr(color=BORDER, thickness=0.5):
        return HRFlowable(width='100%', thickness=thickness, color=color, spaceAfter=4)

    # ── HEADER BAND ──────────────────────────────────────────
    header_data = [[
        para('<font color="#e8192c"><b>e</b></font><font color="#111827"><b>Garage</b></font>',
             styles['Normal'],
             fontSize=22, fontName='Helvetica-Bold'),
        para(
            f'<font color="#e8192c"><b>TAX INVOICE</b></font><br/>'
            f'<font color="#64748b" size="8">#{booking.reference}</font>',
            styles['Normal'], fontSize=12, alignment=TA_RIGHT
        ),
    ]]
    header_table = Table(header_data, colWidths=['60%', '40%'])
    header_table.setStyle(TableStyle([
        ('VALIGN',  (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(header_table)
    story.append(hr(RED, 2))
    story.append(Spacer(1, 4*mm))

    # ── FROM / TO ADDRESSES ──────────────────────────────────
    garage_name  = booking.garage.name    if booking.garage  else 'eGarage'
    garage_addr  = booking.garage.address if booking.garage  else 'Rajkot, Gujarat'
    garage_phone = booking.garage.phone   if booking.garage  else '+91 80000 00000'
    garage_email = booking.garage.email   if booking.garage  else 'support@egarage.in'
    garage_gst   = booking.garage.gst_number if booking.garage and booking.garage.gst_number else '24AADCE9999N1Z4'

    addr_data = [[
        # FROM
        Table([
            [para('<b>FROM</b>', styles['Normal'], fontSize=7, textColor=GREY)],
            [para(f'<b>{garage_name}</b>', styles['Normal'], fontSize=10, textColor=BLACK)],
            [para(garage_addr, styles['Normal'], fontSize=8, textColor=GREY, leading=12)],
            [para(f'Phone: {garage_phone}', styles['Normal'], fontSize=8, textColor=GREY)],
            [para(f'Email: {garage_email}', styles['Normal'], fontSize=8, textColor=GREY)],
            [para(f'GSTIN: {garage_gst}',  styles['Normal'], fontSize=8, textColor=GREY)],
        ], colWidths=['100%']),
        # TO
        Table([
            [para('<b>BILL TO</b>', styles['Normal'], fontSize=7, textColor=GREY)],
            [para(f'<b>{booking.customer_name}</b>', styles['Normal'], fontSize=10, textColor=BLACK)],
            [para(booking.customer_phone, styles['Normal'], fontSize=8, textColor=GREY)],
            [para(booking.customer_email or '—', styles['Normal'], fontSize=8, textColor=GREY)],
            [para(booking.pickup_address or '—', styles['Normal'], fontSize=8, textColor=GREY, leading=12)],
        ], colWidths=['100%']),
        # INVOICE META
        Table([
            [para('<b>INVOICE DETAILS</b>', styles['Normal'], fontSize=7, textColor=GREY)],
            [Table([
                [para('Invoice Date', styles['Normal'], fontSize=8, textColor=GREY),
                 para(date.today().strftime('%d %b %Y'), styles['Normal'], fontSize=8, textColor=BLACK, alignment=TA_RIGHT)],
                [para('Booking Ref',  styles['Normal'], fontSize=8, textColor=GREY),
                 para(booking.reference, styles['Normal'], fontSize=8, textColor=BLUE, alignment=TA_RIGHT)],
                [para('Service Date', styles['Normal'], fontSize=8, textColor=GREY),
                 para(booking.scheduled_date.strftime('%d %b %Y'), styles['Normal'], fontSize=8, textColor=BLACK, alignment=TA_RIGHT)],
                [para('Payment',      styles['Normal'], fontSize=8, textColor=GREY),
                 para(booking.get_payment_status_display(), styles['Normal'], fontSize=8,
                      textColor=GREEN if booking.payment_status=='paid' else GREY, alignment=TA_RIGHT)],
            ], colWidths=['50%','50%'])],
        ], colWidths=['100%']),
    ]]
    addr_table = Table(addr_data, colWidths=['35%', '33%', '32%'])
    addr_table.setStyle(TableStyle([
        ('VALIGN',  (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING',  (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(addr_table)
    story.append(Spacer(1, 5*mm))
    story.append(hr())

    # ── VEHICLE INFO ─────────────────────────────────────────
    if booking.vehicle:
        v = booking.vehicle
        veh_text = f'{v.brand} {v.model_name}'
        if v.variant:       veh_text += f' {v.variant}'
        if v.registration_number: veh_text += f' · Reg: {v.registration_number}'
        if v.fuel_type:     veh_text += f' · {v.get_fuel_type_display()}'
        story.append(Spacer(1, 3*mm))
        story.append(Table([[
            para('🚗 Vehicle:', styles['Normal'], fontSize=8, textColor=GREY),
            para(f'<b>{veh_text}</b>', styles['Normal'], fontSize=9, textColor=BLACK),
        ]], colWidths=['18%', '82%']))
        story.append(Spacer(1, 3*mm))
        story.append(hr())

    # ── LINE ITEMS TABLE ─────────────────────────────────────
    story.append(Spacer(1, 4*mm))

    svc_name = booking.service.name if booking.service else 'Car Service'
    pkg_name = booking.get_package_display()

    col_header_style = ParagraphStyle('ch', parent=styles['Normal'],
                                      fontSize=8, fontName='Helvetica-Bold',
                                      textColor=WHITE)
    col_body_style   = ParagraphStyle('cb', parent=styles['Normal'],
                                      fontSize=9, textColor=BLACK)
    col_right_style  = ParagraphStyle('cr', parent=styles['Normal'],
                                      fontSize=9, textColor=BLACK, alignment=TA_RIGHT)

    items_header = [
        para('#',           col_header_style),
        para('Description', col_header_style),
        para('Package',     col_header_style),
        para('Duration',    col_header_style),
        para('Qty',         col_header_style),
        para('Unit Price',  col_header_style),
        para('Amount',      col_header_style),
    ]

    duration = '—'
    if booking.service and booking.service.duration_hours:
        h = float(booking.service.duration_hours)
        duration = f'{int(h)}h {int((h%1)*60)}m' if h % 1 else f'{int(h)}h'

    items_row = [
        para('1', col_body_style),
        para(f'<b>{svc_name}</b>', col_body_style),
        para(pkg_name,    col_body_style),
        para(duration,    col_body_style),
        para('1',         col_body_style),
        para(f'₹{booking.base_price:,.0f}', col_right_style),
        para(f'₹{booking.base_price:,.0f}', col_right_style),
    ]

    # Pickup row
    rows = [items_header, items_row]
    if booking.pickup_required:
        rows.append([
            para('2', col_body_style),
            para('Pickup & Drop Service', col_body_style),
            para('Included', col_body_style),
            para('—', col_body_style),
            para('1', col_body_style),
            para('FREE', ParagraphStyle('green', parent=col_right_style, textColor=GREEN)),
            para('₹0', col_right_style),
        ])

    # Parts added by mechanic
    try:
        row_num = len(rows)
        for part in booking.job.parts.all():
            row_num += 1
            rows.append([
                para(str(row_num), col_body_style),
                para(f'<b>{part.name}</b>' + (f'<br/><font size="7" color="grey">{part.detail}</font>' if part.detail else ''), col_body_style),
                para('Part/Material', col_body_style),
                para('—', col_body_style),
                para(str(part.quantity), col_body_style),
                para(f'₹{float(part.unit_cost):,.0f}', col_right_style),
                para(f'₹{float(part.cost):,.0f}', col_right_style),
            ])
    except Exception:
        pass

    items_table = Table(rows, colWidths=['6%','34%','12%','12%','6%','15%','15%'])
    items_table.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  DARK),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, LIGHT]),
        ('TEXTCOLOR',     (0,0), (-1,0),  WHITE),
        ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 8),
        ('ALIGN',         (5,0), (-1,-1), 'RIGHT'),
        ('ALIGN',         (4,0), (4,-1),  'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
        ('GRID',          (0,0), (-1,-1), 0.3, BORDER),
        ('ROUNDEDCORNERS',(0,0), (-1,-1), [3,3,3,3]),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 5*mm))

    # ── TOTALS ───────────────────────────────────────────────
    totals = []
    totals.append(['Service Charge', f'₹{booking.base_price:,.0f}'])
    if booking.discount_amount > 0:
        coupon_label = f'Discount ({booking.coupon.code})' if booking.coupon else 'Discount'
        totals.append([coupon_label, f'−₹{booking.discount_amount:,.0f}'])
    # Parts & labour if job has them
    try:
        parts_total = float(getattr(booking, 'parts_total', 0) or 0)
        labour      = float(getattr(booking, 'labour_charge', 0) or 0)
        if parts_total > 0:
            totals.append(['Parts & Materials', f'₹{parts_total:,.0f}'])
        if labour > 0:
            totals.append(['Labour Charges', f'₹{labour:,.0f}'])
    except Exception:
        pass
    totals.append(['GST (18%)', 'Included'])
    # Advance paid
    try:
        advance = float(getattr(booking, 'advance_amount', 0) or 0)
        if advance > 0 and getattr(booking, 'advance_paid', False):
            totals.append([f'Advance Paid ({getattr(booking,"advance_method","online").upper()})',
                           f'−₹{advance:,.0f}'])
    except Exception:
        pass
    # Final total
    try:
        final = float(getattr(booking, 'final_bill', None) or booking.final_price or 0)
        balance = float(getattr(booking, 'balance_due', None) or final or 0)
    except Exception:
        final = float(booking.final_price or 0)
        balance = final
    totals.append([para('<b>TOTAL BILL</b>', styles['Normal'], fontSize=11, textColor=WHITE),
                   para(f'<b>₹{final:,.0f}</b>', styles['Normal'], fontSize=12, textColor=WHITE, alignment=TA_RIGHT)])
    if balance < final and balance > 0:
        totals.append([para('<b>BALANCE DUE AT GARAGE</b>', styles['Normal'], fontSize=10, textColor=WHITE),
                       para(f'<b>₹{balance:,.0f}</b>', styles['Normal'], fontSize=11, textColor=WHITE, alignment=TA_RIGHT)])

    totals_table = Table(
        totals,
        colWidths=['70%', '30%'],
        hAlign='RIGHT',
        style=TableStyle([
            ('ALIGN',          (1,0), (1,-1), 'RIGHT'),
            ('FONTSIZE',       (0,0), (-1,-1), 9),
            ('TOPPADDING',     (0,0), (-1,-1), 5),
            ('BOTTOMPADDING',  (0,0), (-1,-1), 5),
            ('LEFTPADDING',    (0,0), (-1,-1), 10),
            ('RIGHTPADDING',   (0,0), (-1,-1), 10),
            ('LINEBELOW',      (0,-3), (-1,-3), 0.5, BORDER),
            ('BACKGROUND',     (0,-2), (-1,-1), RED),
            ('TEXTCOLOR',      (0,-2), (-1,-1), WHITE),
            ('ROWBACKGROUNDS', (0,0),  (-1,-3), [WHITE, LIGHT]),
        ])
    )
    right_wrapper = Table([[None, totals_table]], colWidths=['40%', '60%'])
    right_wrapper.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    story.append(right_wrapper)
    story.append(Spacer(1, 6*mm))

    # ── WARRANTY BOX ─────────────────────────────────────────
    if booking.service and booking.service.warranty_days:
        war_days = booking.service.warranty_days
        story.append(KeepTogether([
            Table([[
                para(f'🛡️  <b>Warranty:</b> {war_days} days / {int(war_days/30)} months from service date. '
                     f'Free re-service if the same issue recurs within the warranty period.',
                     styles['Normal'], fontSize=8, textColor=DARK)
            ]], colWidths=['100%'],
            style=TableStyle([
                ('BACKGROUND',    (0,0), (-1,-1), colors.HexColor('#f0fdf4')),
                ('LINEAFTER',     (0,0), (0,-1),  3, GREEN),
                ('TOPPADDING',    (0,0), (-1,-1),  8),
                ('BOTTOMPADDING', (0,0), (-1,-1),  8),
                ('LEFTPADDING',   (0,0), (-1,-1),  10),
                ('RIGHTPADDING',  (0,0), (-1,-1),  10),
                ('ROUNDEDCORNERS',(0,0), (-1,-1),  [4,4,4,4]),
            ]))
        ]))
        story.append(Spacer(1, 4*mm))

    # ── NOTES ────────────────────────────────────────────────
    if booking.notes:
        story.append(para(f'<b>Notes:</b> {booking.notes}',
                          styles['Normal'], fontSize=8, textColor=GREY))
        story.append(Spacer(1, 3*mm))

    # ── THANK YOU ────────────────────────────────────────────
    story.append(hr(RED, 1.5))
    story.append(Spacer(1, 3*mm))
    story.append(para(
        '<b>Thank you for choosing eGarage! 🙏</b><br/>'
        '<font size="8" color="#64748b">'
        'For support: support@egarage.in · +91 80000 00000 · www.egarage.in'
        '</font>',
        styles['Normal'], fontSize=10, textColor=BLACK, alignment=TA_CENTER
    ))

    # ── BUILD PDF ────────────────────────────────────────────
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="eGarage-Invoice-{booking.reference}.pdf"'
    )
    return response