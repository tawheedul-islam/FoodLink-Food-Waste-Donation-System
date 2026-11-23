from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.utils import timezone
from donations.models import FoodDonation
from .forms import PickupRequestForm, RatingForm
from .models import DonationRequest, Notification, Rating


from io import BytesIO
from xml.sax.saxutils import escape

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from accounts.models import OrganizationMembership
from donations.models import FoodDonation
from .forms import PickupRequestForm, RatingForm
from .models import DonationRequest, DonationReceipt, Notification, Rating


def _request_access_filter(user):
    if user.role == 'donor':
        return (
            Q(donation__donor=user)
            | Q(donation__organization__memberships__user=user)
        )
    if user.role == 'receiver':
        return (
            Q(receiver=user)
            | Q(receiver_organization__memberships__user=user)
        )
    return Q(pk__in=[])


def requests_with_trust_signals():
    return DonationRequest.objects.select_related(
        'receiver',
        'receiver_organization',
        'donation',
        'donation__donor',
        'donation__organization',
        'receipt',
    ).annotate(
        receiver_completed_pickups=Count(
            'receiver__requests',
            filter=Q(receiver__requests__status='completed'),
            distinct=True,
        ),
        donor_completed_donations=Count(
            'donation__donor__donations',
            filter=Q(donation__donor__donations__status='completed'),
            distinct=True,
        ),
        donor_average_rating=Avg('donation__donor__ratings_received__score'),
        donor_rating_count=Count('donation__donor__ratings_received', distinct=True),
    )


@login_required
def create_request(request, pk):
    donation = get_object_or_404(FoodDonation, pk=pk)

    if request.user.role != 'receiver':
        messages.error(request, 'Only receivers can request donations.')
        return redirect('donation_detail', pk=pk)

    already_requested = DonationRequest.objects.filter(donation=donation, receiver=request.user).exists()
    if already_requested:
        messages.warning(request, 'You have already requested this donation.')
        return redirect('donation_detail', pk=pk)
    if donation.status != 'posted' or donation.expiry_time <= timezone.now():
        messages.error(request, 'This donation is no longer available to request.')
        return redirect('donation_detail', pk=pk)

    if request.method == 'POST':
        form = PickupRequestForm(request.POST, donation=donation, user=request.user)
        if form.is_valid():
            pickup_request = DonationRequest.objects.create(
                donation=donation,
                receiver=request.user,
                receiver_organization=form.cleaned_data['receiver_organization'],
                pickup_time=form.cleaned_data['pickup_time'],
            )
            donation.status = 'requested'
            donation.save(update_fields=['status'])

            local_pickup_time = timezone.localtime(pickup_request.pickup_time)
            Notification.objects.create(
                user=donation.donor,
                message=(
                    f"{request.user.username} requested '{donation.food_name}' "
                    f"{'on behalf of ' + pickup_request.receiver_organization.name + ' ' if pickup_request.receiver_organization else ''}"
                    f"for pickup at {local_pickup_time:%d %b %Y, %H:%M}."
                ),
                donation=donation,
            )
            messages.success(request, 'Pickup request submitted. The donor will confirm your time.')
            return redirect('my_requests')
    else:
        form = PickupRequestForm(donation=donation, user=request.user)

    return render(request, 'requests_app/create_request.html', {
        'form': form,
        'donation': donation,
    })

@login_required
def my_requests(request):
    reqs = requests_with_trust_signals().filter(
        Q(receiver=request.user)
        | Q(receiver_organization__memberships__user=request.user)
    ).order_by('-request_date')
    return render(request, 'requests_app/my_requests.html', {'requests': reqs})

@login_required
def incoming_requests(request):
    if request.user.role != 'donor':
        messages.error(request, 'Only donors can view incoming requests.')
        return redirect('donation_list')
    reqs = requests_with_trust_signals().filter(
        Q(donation__donor=request.user, donation__organization__isnull=True)
        | Q(donation__organization__memberships__user=request.user)
    ).order_by('-request_date')
    return render(request, 'requests_app/incoming_requests.html', {'requests': reqs})

@login_required
def update_request_status(request, pk, new_status):
    if request.method != 'POST':
        messages.error(request, 'Use the request actions to update its status.')
        return redirect('incoming_requests')

    if new_status not in {'accepted', 'rejected', 'completed'}:
        messages.error(request, 'Invalid request status.')
        return redirect('incoming_requests')

    if request.user.role != 'donor':
        messages.error(request, 'Only donors can update incoming requests.')
        return redirect('donation_list')

    req = get_object_or_404(
        DonationRequest.objects.filter(
            Q(donation__donor=request.user, donation__organization__isnull=True)
            | Q(donation__organization__memberships__user=request.user)
        ).distinct(),
        pk=pk,
    )
    if (new_status in {'accepted', 'rejected'} and req.status != 'pending') or (
        new_status == 'completed' and req.status != 'accepted'
    ):
        messages.error(request, 'This request can no longer be updated to that status.')
        return redirect('incoming_requests')
    if new_status == 'accepted' and req.pickup_time and req.pickup_time <= timezone.now():
        messages.error(request, 'The proposed pickup time has passed. Ask the receiver to submit a new request.')
        return redirect('incoming_requests')

    req.status = new_status
    status_time_field = {
        'accepted': 'accepted_at',
        'rejected': 'rejected_at',
        'completed': 'completed_at',
    }[new_status]
    setattr(req, status_time_field, timezone.now())
    req.save(update_fields=['status', status_time_field])

    if new_status == 'accepted':
        req.donation.status = 'accepted'
        req.donation.save()
    elif new_status == 'rejected':
        req.donation.status = 'posted'
        req.donation.save()
    elif new_status == 'completed':
        req.donation.status = 'completed'
        req.donation.save()

    Notification.objects.create(
        user=req.receiver,
        message=(
            f"Your request for '{req.donation.food_name}' was accepted. "
            f"Pickup is confirmed for {timezone.localtime(req.pickup_time):%d %b %Y, %H:%M}."
            if new_status == 'accepted' and req.pickup_time
            else f"Your request for '{req.donation.food_name}' was {new_status}."
        ),
        donation=req.donation
    )
    messages.success(request, f'Request marked as {new_status}.')
    return redirect('incoming_requests')


@login_required
def confirm_receipt(request, pk):
    if request.method != 'POST':
        messages.error(request, 'Use the receipt confirmation button after receiving the donation.')
        return redirect('my_requests')
    if request.user.role != 'receiver':
        messages.error(request, 'Only the receiver can confirm receipt of a donation.')
        return redirect('my_requests')

    pickup_request = get_object_or_404(
        DonationRequest.objects.select_related(
            'receiver',
            'receiver_organization',
            'donation',
            'donation__donor',
            'donation__organization',
        ).filter(_request_access_filter(request.user)).distinct(),
        pk=pk,
        status='completed',
    )

    receipt_values = {
        'donation_name': pickup_request.donation.food_name,
        'quantity': pickup_request.donation.quantity,
        'donor_name': pickup_request.donation.donor.get_full_name() or pickup_request.donation.donor.username,
        'receiver_name': pickup_request.receiver.get_full_name() or pickup_request.receiver.username,
        'donor_organization_name': (
            pickup_request.donation.organization.name
            if pickup_request.donation.organization_id else ''
        ),
        'receiver_organization_name': (
            pickup_request.receiver_organization.name
            if pickup_request.receiver_organization_id else ''
        ),
        'pickup_location': pickup_request.donation.pickup_location,
        'pickup_time': pickup_request.pickup_time,
        'completed_at': pickup_request.completed_at,
    }

    with transaction.atomic():
        receipt, created = DonationReceipt.objects.get_or_create(
            donation_request=pickup_request,
            defaults=receipt_values,
        )
        if created:
            donor_user_ids = {pickup_request.donation.donor_id}
            if pickup_request.donation.organization_id:
                donor_user_ids.update(
                    OrganizationMembership.objects.filter(
                        organization_id=pickup_request.donation.organization_id,
                    ).values_list('user_id', flat=True)
                )
            Notification.objects.bulk_create([
                Notification(
                    user_id=user_id,
                    message=f"Receipt confirmed for '{receipt.donation_name}'. The donation receipt is ready to download.",
                    donation=pickup_request.donation,
                )
                for user_id in donor_user_ids
            ])

    if created:
        messages.success(request, 'Receipt confirmed. Your donation receipt PDF is ready.')
    else:
        messages.info(request, 'Receipt was already confirmed. You can download the existing PDF.')
    return redirect('my_requests')


@login_required
def donation_receipt(request, pk):
    if request.user.role not in {'donor', 'receiver'}:
        return HttpResponseForbidden('Only donation participants can download this receipt.')

    receipt = get_object_or_404(
        DonationReceipt.objects.select_related(
            'donation_request',
            'donation_request__donation',
        ).filter(
            donation_request__in=DonationRequest.objects.filter(
                _request_access_filter(request.user),
            )
        ),
        donation_request_id=pk,
    )

    output = BytesIO()
    page_width, _ = A4
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=19 * mm,
        leftMargin=19 * mm,
        topMargin=17 * mm,
        bottomMargin=21 * mm,
        title=f"FoodLink donation receipt {receipt.receipt_number}",
        author='FoodLink',
        subject='Donation handover acknowledgment',
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='ReceiptBrand',
        parent=styles['BodyText'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name='ReceiptBrandTag',
        parent=styles['BodyText'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#dcefe4'),
    ))
    styles.add(ParagraphStyle(
        name='ReceiptTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=21,
        leading=26,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#173b2b'),
        spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name='ReceiptSubtitle',
        parent=styles['BodyText'],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#64736b'),
    ))
    styles.add(ParagraphStyle(
        name='ReceiptSection',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#146c43'),
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name='ReceiptLabel',
        parent=styles['BodyText'],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#68756e'),
    ))
    styles.add(ParagraphStyle(
        name='ReceiptValue',
        parent=styles['BodyText'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#26352d'),
    ))
    styles.add(ParagraphStyle(
        name='ReceiptNote',
        parent=styles['BodyText'],
        fontSize=8,
        leading=12,
        textColor=colors.HexColor('#4f5f56'),
    ))
    content_width = page_width - 38 * mm
    green = colors.HexColor('#146c43')
    pale_green = colors.HexColor('#edf5f0')
    border = colors.HexColor('#dce6df')

    def field(label, value, value_style='ReceiptValue'):
        return [
            Paragraph(escape(label.upper()), styles['ReceiptLabel']),
            Paragraph(escape(value), styles[value_style]),
        ]

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(border)
        canvas.setLineWidth(.6)
        canvas.line(19 * mm, 16 * mm, page_width - 19 * mm, 16 * mm)
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(colors.HexColor('#68756e'))
        canvas.drawString(19 * mm, 10 * mm, 'FoodLink | Donation handover acknowledgment')
        canvas.drawRightString(page_width - 19 * mm, 10 * mm, f'Page {doc.page}')
        canvas.restoreState()

    story = [
        Table(
            [[
                Paragraph('FoodLink', styles['ReceiptBrand']),
                Paragraph('DONATION RECEIPT', styles['ReceiptBrandTag']),
            ]],
            colWidths=[content_width * .55, content_width * .45],
            style=TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), green),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]),
        ),
        Spacer(1, 8 * mm),
        Paragraph('Donation handover acknowledgment', styles['ReceiptTitle']),
        Paragraph('A record of a completed food donation between the parties below.', styles['ReceiptSubtitle']),
        Spacer(1, 5 * mm),
    ]

    receipt_meta = Table(
        [[
            [
                Paragraph('RECEIPT NUMBER', styles['ReceiptLabel']),
                Paragraph(escape(str(receipt.receipt_number)), styles['ReceiptValue']),
            ],
            [
                Paragraph('ISSUED', styles['ReceiptLabel']),
                Paragraph(
                    timezone.localtime(receipt.issued_at).strftime('%d %b %Y, %H:%M %Z'),
                    styles['ReceiptValue'],
                ),
            ],
        ]],
        colWidths=[content_width * .62, content_width * .38],
        style=TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), pale_green),
            ('BOX', (0, 0), (-1, -1), .7, border),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]),
    )
    story.extend([
        receipt_meta,
        Paragraph('Donation details', styles['ReceiptSection']),
        Table(
            [[field('Food item', receipt.donation_name), field('Quantity', receipt.quantity)]],
            colWidths=[content_width * .62, content_width * .38],
            style=TableStyle([
                ('BOX', (0, 0), (-1, -1), .7, border),
                ('INNERGRID', (0, 0), (-1, -1), .5, border),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
            ]),
        ),
        Paragraph('Parties', styles['ReceiptSection']),
        Table(
            [[
                field('Donated by', receipt.donor_name)
                + field('Organization', receipt.donor_organization_name or 'Individual donor'),
                field('Received by', receipt.receiver_name)
                + field('Organization', receipt.receiver_organization_name or 'Individual receiver'),
            ]],
            colWidths=[content_width / 2, content_width / 2],
            style=TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), pale_green),
                ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#f7f9f7')),
                ('BOX', (0, 0), (-1, -1), .7, border),
                ('INNERGRID', (0, 0), (-1, -1), .5, border),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
            ]),
        ),
        Paragraph('Handover details', styles['ReceiptSection']),
    ])

    handover_rows = [
        ('Pickup location', receipt.pickup_location),
        (
            'Scheduled pickup',
            timezone.localtime(receipt.pickup_time).strftime('%d %b %Y, %H:%M %Z')
            if receipt.pickup_time else 'Not specified',
        ),
        (
            'Marked complete',
            timezone.localtime(receipt.completed_at).strftime('%d %b %Y, %H:%M %Z')
            if receipt.completed_at else 'Not recorded',
        ),
        (
            'Receiver confirmation',
            timezone.localtime(receipt.issued_at).strftime('%d %b %Y, %H:%M %Z'),
        ),
    ]
    handover_table = Table(
        [[Paragraph(escape(label), styles['ReceiptLabel']),
          Paragraph(escape(value), styles['ReceiptValue'])]
         for label, value in handover_rows],
        colWidths=[content_width * .34, content_width * .66],
        style=TableStyle([
            ('LINEBELOW', (0, 0), (-1, -2), .5, border),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]),
    )
    story.extend([
        handover_table,
        Spacer(1, 5 * mm),
        Table(
            [[Paragraph(
                '<b>Receipt confirmation</b><br/>'
                'The receiver confirmed that the donation was received. This document acknowledges a donation handover; '
                'it is not an invoice, proof of payment, or valuation of the donated items.',
                styles['ReceiptNote'],
            )]],
            colWidths=[content_width],
            style=TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), pale_green),
                ('BOX', (0, 0), (-1, -1), .7, border),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
            ]),
        ),
    ])
    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)

    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="foodlink-receipt-{receipt.receipt_number}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
def cancel_request(request, pk):
    req = get_object_or_404(DonationRequest, pk=pk, receiver=request.user)

    if req.status != 'pending':
        messages.error(request, 'You can only cancel pending requests.')
        return redirect('my_requests')

    donation = req.donation
    req.delete()
    donation.status = 'posted'
    donation.save()
    messages.success(request, 'Request cancelled successfully.')
    return redirect('my_requests')

@login_required
def notifications(request):
    notes = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread = notes.filter(is_read=False)
    unread.update(is_read=True)
    return render(request, 'requests_app/notifications.html', {'notifications': notes})

@login_required
def rate_donation(request, pk):
    req = get_object_or_404(DonationRequest, pk=pk, receiver=request.user)

    if req.status != 'completed':
        messages.error(request, 'You can only rate completed donations.')
        return redirect('my_requests')

    if hasattr(req, 'rating'):
        messages.warning(request, 'You have already rated this donation.')
        return redirect('my_requests')

    if request.method == 'POST':
        form = RatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.donation_request = req
            rating.rated_by = request.user
            rating.rated_user = req.donation.donor
            rating.save()
            messages.success(request, 'Thank you for your feedback!')
            return redirect('my_requests')
    else:
        form = RatingForm()
    return render(request, 'requests_app/rate_donation.html', {'form': form, 'req': req})