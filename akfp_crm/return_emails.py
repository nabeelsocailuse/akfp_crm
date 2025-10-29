import frappe
from frappe.utils import get_url

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
