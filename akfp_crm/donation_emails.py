import frappe
from frappe import _
from frappe.utils import get_url
from frappe.utils import today, get_first_day, get_last_day, getdate, nowdate

@frappe.whitelist()
def send_return_donation_email(doc, method):
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

            frappe.logger().info(f"✅ Return Donation Email sent to {row.email} for Donation {doc.name}")

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Donation Return Email Failed")
        frappe.throw(f"Failed to send return donation email. Error: {str(e)}")


@frappe.whitelist()
def send_thank_you_email(doc, method):   ##thank you email to the donor when the payment entry is created for the donation 
    """Send a thank-you email when a payment entry is submitted for a donor."""
    try:
        if doc.party_type != "Donor" or not doc.party:
            return

        donor = frappe.get_doc("Donor", doc.party)
        donor_email = donor.get("email") or donor.get("donor_email")

        if not donor_email:
            frappe.logger().warning(f"No email found for donor {doc.party}")
            return

        subject = _("Thank You for Your Donation")
        message = f"""
        <p>Dear {donor.get('donor_name') or donor.name},</p>
        <p>We have received your generous donation of <b>{frappe.format_value(doc.paid_amount, {'fieldtype': 'Currency'})}</b>.</p>
        <p>Your contribution helps us continue our mission.</p>
        <br>
        <p>With gratitude,<br>{doc.company}</p>
        """

        # Send email
        frappe.sendmail(
            recipients=[donor_email],
            subject=subject,
            message=message,
            reference_doctype="Payment Entry",
            reference_name=doc.name,
            now=True,
        )
        frappe.logger().info(f"✅ Thank You email sent to {donor_email} for Payment Entry {doc.name}")

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Thank You Email Error")




@frappe.whitelist()
def check_sponsorships():
    """
    Run daily, but only act on the last day of the month.
    For each submitted Sponsorship:
      - Check if a Payment Entry exists for its pledges this month
      - If not, send a reminder email to the donor
    """
    current_date = getdate(today())
    last_day = getdate(get_last_day(current_date))

    # Only run on the last day of the month
    if current_date != last_day:
        frappe.logger().info(f"Skipping sponsorship check: today {current_date} is not last day {last_day}")
        return

    first_day = getdate(get_first_day(current_date))
    frappe.logger().info(f"🔍 Running monthly sponsorship reminder check for {first_day} → {last_day}")

    # Fetch all active sponsorships
    sponsorships = frappe.get_all(
        "Sponsorship",
        filters={"docstatus": 1},
        fields=["name", "donor", "student_id", "start_date", "end_date", "total_sponsored_amount"]
    )

    for s in sponsorships:
        # Find pledges linked to this sponsorship
        pledges = frappe.get_all("Pledge", filters={"sponsorship": s.name}, pluck="name")

        if not pledges:
            frappe.logger().info(f"No pledges found for Sponsorship {s.name}")
            continue

        # Check for payment entries for these pledges this month
        payment_exists = frappe.db.exists(
            "Payment Entry",
            {
                "docstatus": 1,
                "reference_doctype": "Pledge",
                "reference_name": ["in", pledges],
                "posting_date": ["between", [first_day, last_day]],
            },
        )

        # If no payment found, send reminder
        if not payment_exists:
            try:
                send_sponsorship_reminder(s)
            except Exception:
                frappe.log_error(frappe.get_traceback(), "Sponsorship Reminder Email Failed")


def send_sponsorship_reminder(s):
    """Send reminder email if no payment recorded for this sponsorship in the month."""
    donor_email = frappe.db.get_value("Donor", s.donor, "email")
    if not donor_email:
        frappe.logger().info(f"❌ No email found for donor {s.donor}")
        return

    message = f"""
    <p>Dear {s.donor},</p>
    <p>We noticed that no payment was received for your sponsorship of student <b>{s.student_id}</b> for this month.</p>
    <p>Please make the payment at your earliest convenience to continue your sponsorship.</p>
    <p><b>Sponsorship ID:</b> {s.name}<br>
    <b>Total Sponsored Amount:</b> {frappe.format_value(s.total_sponsored_amount, {'fieldtype': 'Currency'})}<br>
    <b>Start Date:</b> {s.start_date}<br>
    <b>End Date:</b> {s.end_date}</p>
    <p>Thank you for your continued support and generosity!</p>
    """

    frappe.sendmail(
        recipients=[donor_email],
        subject="Reminder: Sponsorship Payment Pending",
        message=message,
        now=True,
    )

    frappe.logger().info(f"🔔 Reminder email sent to {donor_email} for Sponsorship {s.name}")




import frappe
from frappe.utils import getdate, nowdate

@frappe.whitelist()
def check_sponsorship_expiry():

    today = getdate(nowdate())

    sponsorships = frappe.db.get_all(
        "Sponsorship",
        filters={
            "docstatus": 1,
            "email_sent": 0 
        },
        fields=["name", "donor_id", "end_date"]
    )

    for s in sponsorships:
        if not s.end_date:
            continue

        if today > getdate(s.end_date):
            donor_info = frappe.db.get_value(
                "Donor", s.donor, ["donor_name", "email"], as_dict=True
            )

            if donor_info and donor_info.email:
                send_renewal_email(s.name, donor_info.donor_name, donor_info.email)
                frappe.db.set_value("Sponsorship", s.name, "email_sent", 1)
                frappe.db.commit()


def send_renewal_email(sponsorship_id, donor_name, recipient_email):
    """Send sponsorship renewal email to donor."""

    subject = "Renew Your Sponsorship - Thank You for Your Support ❤️"

    message = f"""
    <p>Dear {donor_name or 'Donor'},</p>

    <p>We hope this message finds you well. Your sponsorship <b>{sponsorship_id}</b> has completed its tenure.</p>

    <p>We invite you to <b>renew your sponsorship</b> and continue making a lasting difference in the lives of those in need.</p>

    <p>
        <a href="https://your-site.com/renew_sponsorship/{sponsorship_id}" 
        style="background-color:#007bff;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;">
        Renew Sponsorship
        </a>
    </p>

    <p>Thank you for your continued generosity and trust.</p>
    <p>Warm regards,<br><b>Alkhidmat Foundation Pakistan</b></p>
    """

    frappe.sendmail(
        recipients=[recipient_email],
        subject=subject,
        message=message
    )
