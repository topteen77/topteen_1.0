"""
Custom storage backends for S3 media.

When S3_MEDIA_ACCESS_MODE is 'proxy', media URLs point to this app (e.g. /media/s3/...)
so only your website can serve the files; the bucket stays private.

When mode is 'cloudfront' (or 'public' with CLOUDFRONT_DOMAIN), django-storages
custom_domain produces https://{CLOUDFRONT_DOMAIN}/... URLs.
"""
from django.conf import settings
from storages.backends.s3 import S3Storage
from storages.utils import clean_name


class S3MediaStorage(S3Storage):
    """
    S3 storage that can return proxy or CloudFront URLs for media.
    Controlled by S3_MEDIA_ACCESS_MODE ('presigned', 'public', 'cloudfront', or 'proxy').
    """

    def url(self, name, parameters=None, expire=None, http_method=None):
        mode = getattr(settings, 'S3_MEDIA_ACCESS_MODE', 'presigned')
        if mode == 'proxy':
            # Serve via Django proxy: only your site can show the file.
            # Use path relative to location (name as stored in FileField); proxy view adds location to get S3 key.
            from django.utils.encoding import filepath_to_uri
            from urllib.parse import quote
            relative = clean_name(name)
            path = quote(filepath_to_uri(relative), safe='/')
            return f'/media/s3/{path}'
        # cloudfront / public / presigned: parent uses custom_domain when configured
        return super().url(name, parameters=parameters, expire=expire, http_method=http_method)
