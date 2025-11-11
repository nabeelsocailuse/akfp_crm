# Copyright (c) 2025, nabeel saleem
# For license information, please see license.txt

import frappe
import base64
import qrcode
import io
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url, getdate, nowdate, today
from frappe.core.doctype.communication.email import make
from frappe import _


class TaxExemptionCertificate(Document):
    def validate(self):
        self.validate_date_of_issue()
        self.make_donor_readonly()
        self.validate_total_donation()

    def validate_date_of_issue(self):
        """Ensure date of issue is not earlier than today."""
        if not self.date_of_issue:
            return
        today_date = getdate(nowdate())
        issue_date = getdate(self.date_of_issue)
        if issue_date < today_date:
            frappe.throw(_("Date of Issue cannot be earlier than today."), title=_("Invalid Date"))

    def make_donor_readonly(self):
        """Donor cannot be changed after creation."""
        if not self.is_new() and self.has_value_changed("donor"):
            frappe.throw(_("Donor field cannot be changed after creation."), title=_("Read-Only Field"))

    def validate_total_donation(self):
        """Ensure total donation is positive."""
        amount_str = str(self.total_donation or "0").replace(",", "").strip()
        amount = float(amount_str or 0)
        if amount <= 0:
            frappe.throw(
                _("Total donation is zero. Cannot create a Tax Exemption Certificate without a positive donation amount."),
                title=_("Invalid Total Donation")
            )


    def before_insert(self):
        """Auto-generate certificate number and timestamp."""
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

    def get_qr_code(self):
        """Generate QR code for verification URL."""
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


@frappe.whitelist()
def get_total_donation(donor, fiscal_year=None, currency=None):
    """Get total valid donations for a donor for a given fiscal year and currency."""
    if not donor:
        return {"total_donation": 0, "message": _("Please select a donor first.")}
    if not fiscal_year:
        return {"total_donation": 0, "message": _("Please select a fiscal year.")}

    if not currency:
        currency = frappe.db.get_value("Donor", donor, "default_currency")
    if not currency:
        return {"total_donation": 0, "message": _("Currency not specified or missing in donor record.")}

    fy = frappe.db.get_value(
        "Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
    )
    if not fy:
        return {"total_donation": 0, "message": _("Fiscal Year not found.")}

    result = frappe.db.sql(
        """
        SELECT 
            SUM(IFNULL(credit_in_transaction_currency, credit_in_account_currency)) AS cr,
            SUM(IFNULL(debit_in_transaction_currency, debit_in_account_currency)) AS dr
        FROM `tabGL Entry`
        WHERE
            is_cancelled = 0
            AND against_voucher_type = 'Donation'
            AND donor = %s
            AND fiscal_year = %s
            AND transaction_currency = %s
            AND (IFNULL(party_type, '') = '' OR party_type IS NULL)
        """,
        (donor, fiscal_year, currency),
        as_dict=True,
    )

    total_donation = (result[0].cr or 0) - (result[0].dr or 0) if result else 0
    if total_donation <= 0:
        return {
            "total_donation": 0,
            "message": _("No valid donation amount found for donor '{0}' in fiscal year '{1}' for currency '{2}'.")
            .format(donor, fiscal_year, currency),
        }

    return {"total_donation": total_donation, "currency": currency}


@frappe.whitelist()
def generate_all_certificates():
    """Generate Tax Exemption Certificates for all donors in the current fiscal year."""
    today_date = nowdate()
    fiscal_year = frappe.db.get_value(
        "Fiscal Year",
        {"year_start_date": ["<=", today_date], "year_end_date": [">=", today_date]},
        "name"
    )
    if not fiscal_year:
        return _("No active Fiscal Year found for today.")

    fy = frappe.get_doc("Fiscal Year", fiscal_year)
    donors = frappe.db.sql(
        """
        SELECT 
            donor,
            transaction_currency AS account_currency,
            SUM(IFNULL(credit_in_transaction_currency, credit_in_account_currency)) AS cr,
            SUM(IFNULL(debit_in_transaction_currency, debit_in_account_currency)) AS dr
        FROM `tabGL Entry`
        WHERE
            is_cancelled = 0
            AND against_voucher_type = 'Donation'
            AND IFNULL(donor, '') != ''
            AND fiscal_year = %s
            AND (IFNULL(party_type, '') = '' OR party_type IS NULL)
        GROUP BY donor, transaction_currency
        HAVING (SUM(IFNULL(credit_in_transaction_currency, credit_in_account_currency)) -
                SUM(IFNULL(debit_in_transaction_currency, debit_in_account_currency))) > 0
        """,
        (fiscal_year,),
        as_dict=True,
    )

    if not donors:
        return _("No donors found with valid donations in the current fiscal year.")

    created, skipped = [], []

    for d in donors:
        donor, currency = d.donor, d.account_currency
        total_donation = (d.cr or 0) - (d.dr or 0)

        if frappe.db.exists("Tax Exemption Certificate", {"donor": donor, "fiscal_year": fiscal_year, "currency": currency}):
            skipped.append(f"{donor} ({currency})")
            continue

        donor_doc = frappe.get_doc("Donor", donor)
        cert = frappe.get_doc({
            "doctype": "Tax Exemption Certificate",
            "donor": donor,
            "donor_name": donor_doc.donor_name,
            "donor_address": donor_doc.address,
            "donor_cnic__ntn": donor_doc.cnic,
            "currency": currency,
            "fiscal_year": fiscal_year,
            "date_of_issue": nowdate(),
            "total_donation": total_donation,
            "generated_timestamp": now_datetime()
        })
        cert.insert(ignore_permissions=True)
        created.append(cert.name)

        if donor_doc.email:
            pdf_file = frappe.get_print(
                doctype="Tax Exemption Certificate",
                name=cert.name,
                print_format="Tax Exemption Certificate format",
                as_pdf=True
            )
            make(
                recipients=donor_doc.email,
                subject=f"Tax Exemption Certificate - {cert.certificate_number}",
                content=f"Dear {donor_doc.donor_name},<br><br>Please find attached your Tax Exemption Certificate for fiscal year {fy.name}.",
                attachments=[{"fname": f"{cert.certificate_number}.pdf", "fcontent": pdf_file}],
                doctype="Tax Exemption Certificate",
                name=cert.name
            )

    frappe.db.commit()

    msg = _("Created {0} Certificates. Skipped {1}.").format(len(created), len(skipped))
    if created:
        msg += "<br><b>Created:</b><br>" + "<br>".join(created)
    if skipped:
        msg += "<br><b>Skipped:</b><br>" + "<br>".join(skipped)
    return msg


@frappe.whitelist(allow_guest=True)
def get_certificate_details(name=None):
    """Public API endpoint to fetch certificate details via QR verification."""
    if not name:
        return {"valid": False, "message": "No certificate ID specified."}
    cert = frappe.db.get("Tax Exemption Certificate", name)
    if not cert:
        return {"valid": False, "message": "Certificate not found."}

    if "total_donation" in cert:
        cert["total_donation"] = float(cert["total_donation"] or 0)
    if "generated_timestamp" in cert and cert["generated_timestamp"]:
        cert["generated_timestamp"] = str(cert["generated_timestamp"])

    return {"valid": True, "certificate": cert}


@frappe.whitelist()
def daily_tax_certificate_job():
    try:
        settings = frappe.get_doc("FCRM Settings")
        if not getattr(settings, "enable", False):
            return "Automation disabled in FCRM Settings."

        today_date = getdate(today())
        fiscal_year = frappe.db.get_value(
            "Fiscal Year",
            {"year_start_date": ("<=", today_date), "year_end_date": (">=", today_date), "disabled": 0},
            ["name", "year_end_date"],
            as_dict=True
        )

        if not fiscal_year:
            return f"No active fiscal year found for today ({today_date})."

        fiscal_year_name = fiscal_year.name
        fiscal_year_end = getdate(fiscal_year.year_end_date)

        if today_date == fiscal_year_end:
            result = generate_all_certificates()
            frappe.db.commit()
            return f"✅ Certificates generated for fiscal year {fiscal_year_name}. Result: {result}"

        return f"Not the last day of fiscal year {fiscal_year} - no action taken."

    except Exception as e:
        error_msg = f"❌ Error in daily tax certificate job: {str(e)}"
        frappe.log_error(error_msg, "Tax Certificate Job Error")
        return error_msg
