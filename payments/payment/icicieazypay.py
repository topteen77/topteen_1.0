from django.conf import settings
from Crypto.Cipher import AES
from base64 import b64decode
from base64 import b64encode


BLOCK_SIZE = 16  # Bytes
pad = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * \
                chr(BLOCK_SIZE - len(s) % BLOCK_SIZE)
unpad = lambda s: s[:-ord(s[len(s) - 1:])]


class AESCipher:
    """
    Usage:
        c = AESCipher('password').encrypt('message')
        m = AESCipher('password').decrypt(c)
    Tested under Python 3 and PyCrypto 2.6.1.
    """

    def __init__(self):
        self.key = settings.ICICI_EAZYPAY_ENCRYPTION_KEY

    def encrypt(self, raw):
        raw = pad(raw)
        cipher = AES.new(self.key, AES.MODE_ECB)
        return b64encode(cipher.encrypt(raw.encode('utf8')))

    def decrypt(self, enc):
        enc = b64decode(enc)
        cipher = AES.new(self.key, AES.MODE_ECB)
        return unpad(cipher.decrypt(enc)).decode('utf8')

class IciciEazyPayService:
    def __init__(self):
        self._merchant_id=str(settings.ICICI_EAZYPAY_MERCHANT_ID)
        self._encryption_key=str(settings.ICICI_EAZYPAY_ENCRYPTION_KEY)
        self._payment_mode=str(settings.ICICI_EAZYPAY_PAYMENT_MODE)
        self._default_base_url=str(settings.ICICI_EAZYPAY_DEFAULT_BASE_URL)
        self._return_url=str(settings.ICICI_EAZYPAY_BASE_RETURN_URL)
        
    def get_encrypt_payment_url(self,reference_no,sub_merchant_id,transaction_amount,email,login_user_id,mobile_no="1111111111",remarks="x",purchase_item="x",order_no_1="x",order_no="x",upivpa="upivpa"):
        mandatory_fields="{}|{}|{}|{}|{}|{}".format(reference_no,sub_merchant_id,transaction_amount,mobile_no,email,login_user_id)
        optional_fields="{}|{}|{}|{}|{}".format(purchase_item,remarks,order_no_1,order_no,upivpa)
        print("#"*30)
        print("{}merchantid={}&mandatory fields={}&optional fields={}&returnurl={}&Reference No={}&submerchantid={}&transaction amount={}&paymode={}".format(self._default_base_url,self._merchant_id,mandatory_fields,optional_fields,self._return_url,reference_no,sub_merchant_id,transaction_amount,self._payment_mode))
        print("#"*30)
        enc_mandatory_fields=self.get_encrypt_value(mandatory_fields)
        enc_optional_fields=self.get_encrypt_value(optional_fields)
        enc_return_url=self.get_encrypt_value(self._return_url)
        enc_reference_no=self.get_encrypt_value(reference_no)
        enc_sub_merchant_id=self.get_encrypt_value(sub_merchant_id)
        enc_transaction_amount=self.get_encrypt_value(transaction_amount)
        enc_payment_mode=self.get_encrypt_value(self._payment_mode)
        enc_url="{}merchantid={}&mandatory fields={}&optional fields={}&returnurl={}&Reference No={}&submerchantid={}&transaction amount={}&paymode={}".format(self._default_base_url,self._merchant_id,enc_mandatory_fields,enc_optional_fields,enc_return_url,enc_reference_no,enc_sub_merchant_id,enc_transaction_amount,enc_payment_mode)
        return enc_url
    
    def get_encrypt_value(self,value):
        return str(AESCipher().encrypt(value))[2:-1]
    
    def get_dcrypt_value(self,value):
        value=bytes(value)
        return AESCipher().decrypt(value)

