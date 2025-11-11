import frappe
from frappe import _
from frappe.utils import (
    get_url,
    today,
    get_first_day,
    get_last_day,
    getdate,
    nowdate,
    add_days,
)

@frappe.whitelist()
def send_return_donation_email(doc, method):  ##when return donaion should send return email to the donor 
    try:
        if isinstance(doc, str):
            doc = frappe.get_doc("Donation", doc)

        if not getattr(doc, "is_return", 0):
            return

        for row in doc.get("payment_detail", []):
            subject = f"Return Donation Confirmation - {doc.name}"
            message = f"""
                <p>Dear {row.donor_name},</p>
                <p>We would like to inform you that a return donation has been processed for your earlier contribution.</p>

                <p><b>Details:</b></p>
                <ul>
                    <li><b>Donation Reference:</b> {doc.return_against or "N/A"}</li>
                    <li><b>Return Amount:</b> {row.donation_amount}</li>
                    <li><b>Fund Class:</b> {row.fund_class}</li>
                    <li><b>Campaign:</b> {doc.campaign or "N/A"}</li>
                </ul>

                <p>You can view the full details <a href="{get_url(doc.get_url())}">here</a>.</p>

                <p>Thank you for your continued support.</p>
                <br>
                <p>Best regards,<br>
                <b>{frappe.defaults.get_global_default("company")}</b></p>
            """

            frappe.sendmail(
                recipients=[row.email],
                subject=subject,
                message=message,
                reference_doctype=doc.doctype,
                reference_name=doc.name,
                now=True  
            )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Donation Return Email Failed")
        frappe.throw(f"Failed to send return donation email. Error: {str(e)}")


@frappe.whitelist()
def send_thank_you_email(doc, method):   ##thank you email to the donor when the payment entry is created for the donation 
    try:
        if doc.party_type != "Donor" or not doc.party:
            return

        donor = frappe.get_doc("Donor", doc.party)
        donor_email = donor.get("email") or donor.get("donor_email")

        if not donor_email:
            return

        currency = getattr(doc, "paid_from_account_currency", None)
        if not currency:
            currency = frappe.db.get_value("Company", doc.company, "default_currency") or "PKR"
        
        formatted_amount = frappe.utils.fmt_money(
            doc.paid_amount,
            currency=currency
        )

        subject = _("Thank You for Your Donation")
        message = f"""
        <p>Dear {donor.get('donor_name') or donor.name},</p>
        <p>We have received your generous donation of <b>{formatted_amount}</b>.</p>
        <p>Your contribution helps us continue our mission.</p>
        <br>
        <p>With gratitude,<br>{doc.company}</p>
        """

        frappe.sendmail(
            recipients=[donor_email],
            subject=subject,
            message=message,
            reference_doctype="Payment Entry",
            reference_name=doc.name,
            now=True,
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Thank You Email Error")


@frappe.whitelist()
def send_sponsorship_closed_email(doc, method=None):  ## when the due_date is less then today make the status closed and send email to the donor

    try:
        if isinstance(doc, str):
            doc = frappe.get_doc("Sponsorship", doc)

        if getattr(doc, "custom_status", None) != "Closed":
            return

        recipient_email = _get_donor_email_from_sponsorship(doc)
        if not recipient_email:
            return

        donor_id = getattr(doc, "donor_id", None) or getattr(doc, "donor", "")
        donor_name = getattr(doc, "donor_name", None) or (donor_id or "Donor")

        subject = f"Sponsorship Closed - {doc.name}"
        message = f"""
        <p>Dear {frappe.utils.escape_html(donor_name)},</p>

        <p>We hope this message finds you well.</p>

        <p>
            Your sponsorship has recently concluded, and we sincerely thank you for your generous support.
            Your contribution has made a meaningful difference.
        </p>

        <p>
            If you would like to continue your sponsorship and keep supporting our initiatives, 
            you can easily renew your sponsorship at your convenience.
            <a href="{get_url(doc.get_url())}">here</a>.
        </p>

        <p>Thank you once again for being a valued supporter.</p>
        """

        frappe.sendmail(
            recipients=[recipient_email],
            subject=subject,
            message=message,
            reference_doctype=doc.doctype,
            reference_name=doc.name,
            now=True,
        )

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Sponsorship Closed Email Failed")


@frappe.whitelist()
def close_expired_sponsorships():

    today_date = getdate(today())

    names = frappe.get_all(
        "Sponsorship",
        filters={
            "end_date": ["<", today_date],
            "custom_status": ["!=", "Closed"],
        },
        pluck="name",
    )

    if not names:
        return

    for name in names:
        try:
            doc = frappe.get_doc("Sponsorship", name)
            if not doc.end_date or getdate(doc.end_date) >= today_date:
                continue
            if getattr(doc, "custom_status", None) == "Closed":
                continue

            doc.custom_status = "Closed"
            doc.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Failed closing expired Sponsorship {name}")


def _get_donor_email_from_sponsorship(doc):
    for field in ("email", "donor_email"):
        val = getattr(doc, field, None)
        if val:
            return val
    donor_link = getattr(doc, "donor_id", None) or getattr(doc, "donor", None)
    if donor_link:
        email_val = frappe.db.get_value("Donor", donor_link, "email")
        if email_val:
            return email_val
    return None


def send_pledge_reminder_emails():   ##when pledge is unpaid and due date is yesterday send reminder email to the donor runs everyday
    try:
        today_date = getdate(today())
        yesterday_date = add_days(today_date, -1)
        
        donations = frappe.get_all(
            "Donation",
            filters={
                "contribution_type": "Pledge",
                "status": "Unpaid",
                "docstatus": 1,
                "due_date": yesterday_date,
            },
            fields=["name", "company", "due_date", "currency"],
        )
        
        if not donations:
            return
        
        company_name = frappe.defaults.get_global_default("company")
        
        for donation in donations:
            try:
                payment_details = frappe.get_all(
                    "Payment Detail",
                    filters={
                        "parent": donation.name,
                    },
                    fields=["name", "donor", "donor_name", "email", "donation_amount", "outstanding_amount"],
                )
                
                if not payment_details:
                    continue
                
                donation_doc = frappe.get_doc("Donation", donation.name)
                donation_url = get_url(donation_doc.get_url())
                
                for payment_detail in payment_details:
                    donor_email = payment_detail.get("email")
                    
                    if not donor_email:
                        continue
                    
                    donor_name = payment_detail.get("donor_name") or "Valued Donor"
                    donation_amount = payment_detail.get("donation_amount", 0)
                    outstanding_amount = payment_detail.get("outstanding_amount", 0)
                    
                    # Format currency
                    currency = donation.get("currency") or frappe.db.get_value(
                        "Company", donation.get("company"), "default_currency"
                    ) or "PKR"
                    
                    formatted_amount = frappe.utils.fmt_money(
                        donation_amount,
                        currency=currency
                    )
                    formatted_outstanding = frappe.utils.fmt_money(
                        outstanding_amount,
                        currency=currency
                    )
                    
                    subject = f"Reminder: Pledge Payment Due - {donation.name}"
                    message = f"""
                        <p>Dear {frappe.utils.escape_html(donor_name)},</p>
                        
                        <p>We hope this message finds you well.</p>
                        
                        <p>
                            This is a friendly reminder that your pledge payment was due on 
                            <b>{frappe.format_date(donation.due_date)}</b> and is currently unpaid.
                        </p>
                        
                        <p><b>Pledge Details:</b></p>
                        <ul>
                            <li><b>Pledge Reference:</b> {donation.name}</li>
                            <li><b>Pledge Amount:</b> {formatted_amount}</li>
                            <li><b>Outstanding Amount:</b> {formatted_outstanding}</li>
                            <li><b>Due Date:</b> {frappe.format_date(donation.due_date)}</li>
                        </ul>
                        
                        <p>
                            We would greatly appreciate your prompt payment to help us continue our mission.
                            You can view the full details of your pledge 
                            <a href="{donation_url}">here</a>.
                        </p>
                        
                        <p>Thank you for your continued support and generosity.</p>
                        <br>
                        <p>Best regards,<br>
                        <b>{company_name or donation.get("company")}</b></p>
                    """
                    
                    frappe.sendmail(
                        recipients=[donor_email],
                        subject=subject,
                        message=message,
                        reference_doctype="Donation",
                        reference_name=donation.name,
                        now=True,
                    )
                    
            except Exception as e:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Failed to send pledge reminder email for Donation {donation.name}"
                )
                continue
                
    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Pledge Reminder Email Job Failed"
        )

