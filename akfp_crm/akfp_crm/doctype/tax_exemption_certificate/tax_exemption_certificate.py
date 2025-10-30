# Copyright (c) 2025, nabeel saleem
# For license information, please see license.txt

import frappe
import base64
import qrcode
import io
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url, getdate, nowdate
from frappe.core.doctype.communication.email import make
from frappe import _


class TaxExemptionCertificate(Document):
    def validate(self):
        self.validate_date_of_issue()
        self.make_donor_readonly()

    def validate_date_of_issue(self): ## date of issue should not be less then today 
        if not self.date_of_issue:
            return

        today = getdate(nowdate())
        issue_date = getdate(self.date_of_issue)

        if issue_date < today:
            frappe.throw(
                _("Date of Issue cannot be earlier than today."),
                title=_("Invalid Date")
            )


    def make_donor_readonly(self):
        if not self.is_new() and self.has_value_changed("donor"):
            frappe.throw(
                _("Donor field cannot be changed after creation."),
                title=_("Read-Only Field")
            )        


    def before_insert(self):
        if not self.certificate_number:
            current_year = now_datetime().year
            prefix = f"TEX-{current_year}-"

            last_cert = frappe.db.sql(
                """
                SELECT certificate_number 
                FROM `tabTax Exemption Certificate`
                WHERE certificate_number LIKE %s
                ORDER BY certificate_number DESC
                LIMIT 1
                """,
                (f"{prefix}%",),
                as_dict=True,
            )

            last_number = (
                int(last_cert[0].certificate_number.split("-")[-1]) + 1
                if last_cert
                else 1
            )
            self.certificate_number = f"{prefix}{last_number:03d}"

        if not self.generated_timestamp:
            self.generated_timestamp = now_datetime()

    def get_qr_code(self):  ##generate qr code 
        url = get_url(f"/verify-certificate?name={self.name}")
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=8,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()



# import frappe
# from frappe.utils import nowdate, now_datetime, _
# from frappe.core.doctype.communication.email import make

@frappe.whitelist()
def get_total_donation(donor, fiscal_year=None):
    """Get total valid donations for a donor using finalized GL Entry query."""
    if not donor:
        return {"total_donation": 0, "message": _("Please select a donor first.")}
    if not fiscal_year:
        return {"total_donation": 0, "message": _("Please select a fiscal year.")}

    fy = frappe.db.get_value(
        "Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
    )
    if not fy:
        return {"total_donation": 0, "message": _("Fiscal Year not found.")}

    # ✅ Use finalized query logic
    result = frappe.db.sql(
        """
        SELECT 
            donor,
            (SELECT donor_name FROM `tabDonor` WHERE name = gl.donor) AS donor_name,
            account_currency,
            fiscal_year,
            SUM(credit_in_account_currency) AS cr
        FROM `tabGL Entry` gl
        WHERE
            is_cancelled = 0
            AND against_voucher_type = 'Donation'
            AND IFNULL(donor, '') != ''
            AND gl.donor = %s
            AND gl.fiscal_year = %s
        GROUP BY donor, account_currency, fiscal_year
        """,
        (donor, fiscal_year),
        as_dict=True,
    )

    total_donation = result[0].cr if result else 0

    if not total_donation or total_donation <= 0:
        return {
            "total_donation": 0,
            "message": _("No valid donation amount found for donor '{0}' in fiscal year '{1}'.").format(
                donor, fiscal_year
            ),
        }

    return {"total_donation": total_donation}


@frappe.whitelist()
def generate_all_certificates():
    """Generate tax exemption certificates, create PDF, and send email to donors."""
    today = frappe.utils.nowdate()
    fiscal_year = frappe.db.get_value(
        "Fiscal Year",
        {"year_start_date": ["<=", today], "year_end_date": [">=", today]},
        "name"
    )

    if not fiscal_year:
        frappe.throw(_("No active Fiscal Year found for today."))

    fy = frappe.get_doc("Fiscal Year", fiscal_year)

    # ✅ Use finalized query for fetching all donors’ total donations
    donors = frappe.db.sql(
        """
        SELECT 
            donor,
            (SELECT donor_name FROM `tabDonor` WHERE name = gl.donor) AS donor_name,
            account_currency,
            fiscal_year,
            SUM(credit_in_account_currency) AS cr
        FROM `tabGL Entry` gl
        WHERE
            is_cancelled = 0
            AND against_voucher_type = 'Donation'
            AND IFNULL(donor, '') != ''
            AND gl.fiscal_year = %s
        GROUP BY donor, account_currency, fiscal_year
        HAVING cr > 0
        """,
        (fiscal_year,),
        as_dict=True,
    )

    if not donors:
        return _("No donors found with valid donations in the current fiscal year.")

    created = []
    skipped = []

    for d in donors:
        donor = d.donor
        total_donation = d.cr or 0

        exists = frappe.db.exists("Tax Exemption Certificate", {"donor": donor, "fiscal_year": fiscal_year})
        if exists:
            skipped.append(donor)
            continue

        donor_doc = frappe.get_doc("Donor", donor)

        cert = frappe.get_doc({
            "doctype": "Tax Exemption Certificate",
            "donor": donor,
            "donor_name": donor_doc.donor_name,
            "donor_address": donor_doc.address,
            "donor_cnic__ntn": donor_doc.cnic,
            "currency": donor_doc.default_currency,
            "fiscal_year": fiscal_year,
            "date_of_issue": nowdate(),
            "total_donation": total_donation,
            "generated_timestamp": now_datetime()
        })
        cert.insert(ignore_permissions=True)
        created.append(cert.name)

        pdf_file = frappe.get_print(
            doctype="Tax Exemption Certificate",
            name=cert.name,
            print_format="Tax Exemption Certificate format",
            as_pdf=True
        )

        if donor_doc.email:
            make(
                recipients=donor_doc.email,
                subject=f"Tax Exemption Certificate - {cert.certificate_number}",
                content=f"Dear {donor_doc.donor_name},<br><br>Please find attached your Tax Exemption Certificate for fiscal year {fy.name}.",
                attachments=[{"fname": f"{cert.certificate_number}.pdf", "fcontent": pdf_file}],
                doctype="Tax Exemption Certificate",
                name=cert.name
            )

    frappe.db.commit()

    msg = _("Created {0} Tax Exemption Certificates. Skipped {1} donors.").format(len(created), len(skipped))
    if created:
        msg += "<br><b>Created Certificates:</b><br>" + "<br>".join(created)
    if skipped:
        msg += "<br><b>Skipped Donors:</b><br>" + "<br>".join(skipped)

    return msg


@frappe.whitelist(allow_guest=True)
def get_certificate_details(name=None):
    """API endpoint to fetch certificate details for verification page / QR code."""
    if not name:
        return {"valid": False, "message": "No certificate ID specified."}
    cert = frappe.db.get("Tax Exemption Certificate", name)
    if not cert:
        return {"valid": False, "message": "Certificate not found."}

    if "total_donation" in cert:
        cert["total_donation"] = float(cert["total_donation"]) if cert["total_donation"] is not None else 0
    if "generated_timestamp" in cert and cert["generated_timestamp"]:
        cert["generated_timestamp"] = str(cert["generated_timestamp"])

    result = {
        "valid": True,
        "certificate": cert
    }
    return result


@frappe.whitelist()
def daily_tax_certificate_job():  ##only generate the certificates on last day of fiscal year
    settings = frappe.get_doc("FCRM Settings")
    if not getattr(settings, "enable", False):
        return "Automation disabled in FCRM Settings."

    today = frappe.utils.nowdate()

    fiscal_year = frappe.db.get_value(
        "Fiscal Year",
        {"year_start_date": ["<=", today], "year_end_date": [">=", today]},
        "name"
    )

    if not fiscal_year:
        return "No active Fiscal Year found for today."

    fy = frappe.get_doc("Fiscal Year", fiscal_year)

    if str(today) != str(fy.year_end_date):
        return f"Not the end of fiscal year ({fy.year_end_date}). Skipping certificate generation."

    result = generate_all_certificates()

    return f"Tax certificate process executed for fiscal year {fiscal_year}. Result: {result}"

