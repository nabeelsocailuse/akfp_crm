# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import random
import string
import base64
import qrcode
import io
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url


class TaxExemptionCertificate(Document): 
    def before_insert(self):
        if not self.certificate_number:
            random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            self.certificate_number = f"CERT-{random_part}"

        if not self.generated_timestamp:
            self.generated_timestamp = now_datetime()

    def get_qr_code(self):
        """Generate a base64 QR code for this certificate"""
        url = get_url(f"/crm/tax-exemption-certificates/{self.name}")


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
        qr_png = buf.getvalue()

        return "data:image/png;base64," + base64.b64encode(qr_png).decode()

    
@frappe.whitelist(allow_guest=True)
def verify_certificate(cert_no: str):

    cert = frappe.get_all(
        "Tax Exemption Certificate",
        filters={"certificate_number": cert_no},
        fields=[
            "name",
            "certificate_number",
            "donor",
            "donor_address",
            "donor_cnic__ntn",
            "donation_date",
            "date_of_issue",
            "total_donation",
            "payment_method",
            "generated_timestamp",
        ],
        limit=1,
    )

    if not cert:
        return {"valid": False, "message": "Certificate not found"}

    return {
        "valid": True,
        "certificate": cert[0],
    }
