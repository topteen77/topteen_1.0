"""
S3 Upload Utility for handling file uploads to AWS S3 bucket
"""
import os
import boto3
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from core.models import Configuration, S3FileUpload
import mimetypes
from urllib.parse import urljoin


class S3UploadService:
    """
    Service class for handling S3 file uploads
    """
    
    def __init__(self):
        """Initialize S3 client with credentials from settings"""
        self.aws_access_key_id = getattr(settings, 'AWS_ACCESS_KEY_ID', '')
        self.aws_secret_access_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', '')
        self.aws_region = getattr(settings, 'AWS_REGION', 'ap-northeast-1')
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'topteenc')
        self.s3_base_url = getattr(settings, 'S3_BUCKET_BASE_URL', 'https://topteenc.s3.ap-northeast-1.amazonaws.com/')
        
        # Initialize S3 client
        try:
            if self.aws_access_key_id and self.aws_secret_access_key:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    region_name=self.aws_region
                )
            else:
                # Try to use default credentials (IAM role, environment variables, etc.)
                self.s3_client = boto3.client('s3', region_name=self.aws_region)
        except Exception as e:
            self.s3_client = None
            print(f"Error initializing S3 client: {e}")
    
    def is_enabled(self):
        """Check if S3 upload is enabled via Configuration"""
        try:
            enabled = Configuration.get('S3_UPLOAD_ENABLED', default='false', editable=True)
            return enabled.lower() == 'true'
        except:
            return False
    
    def get_max_file_size(self):
        """Get maximum file size from environment variable (in bytes)"""
        max_size_mb = getattr(settings, 'S3_MAX_FILE_SIZE_MB', 2)  # Default 2MB
        return max_size_mb * 1024 * 1024  # Convert MB to bytes
    
    def upload_file(self, file_obj, folder_path='', file_name=None, description='', uploaded_by=''):
        """
        Upload a file to S3 bucket
        
        Args:
            file_obj: Django UploadedFile object or file-like object
            folder_path: Optional folder path in S3 (e.g., 'ebook/pdf', 'images/cover')
            file_name: Optional custom file name (defaults to original filename)
            description: Optional description for the file
            uploaded_by: Optional user identifier who uploaded the file
        
        Returns:
            dict with 'success' (bool), 's3_url' (str), 's3_key' (str), 'error' (str)
        """
        if not self.is_enabled():
            return {
                'success': False,
                'error': 'S3 upload is disabled. Enable it in Configuration.'
            }
        
        if not self.s3_client:
            return {
                'success': False,
                'error': 'S3 client not initialized. Check AWS credentials.'
            }
        
        try:
            # Get file name
            if file_name is None:
                if isinstance(file_obj, UploadedFile):
                    file_name = file_obj.name
                else:
                    file_name = os.path.basename(getattr(file_obj, 'name', 'uploaded_file'))
            
            # Clean file name (remove path separators)
            file_name = os.path.basename(file_name)
            
            # Add timestamp to filename to ensure uniqueness
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')  # Format: YYYYMMDD_HHMMSS_microseconds
            name, ext = os.path.splitext(file_name)
            file_name = f"{name}_{timestamp}{ext}"
            
            # Build S3 key (path in bucket)
            if folder_path:
                folder_path = folder_path.strip('/')
                s3_key = f"{folder_path}/{file_name}"
            else:
                s3_key = file_name
            
            # Get file content and validate size
            if isinstance(file_obj, UploadedFile):
                file_size = file_obj.size
                # Validate file size
                max_size = self.get_max_file_size()
                if file_size > max_size:
                    max_size_mb = max_size / (1024 * 1024)
                    return {
                        'success': False,
                        'error': f'File size ({file_size / (1024 * 1024):.2f} MB) exceeds maximum allowed size ({max_size_mb} MB).'
                    }
                file_content = file_obj.read()
                content_type = file_obj.content_type or mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
            else:
                file_content = file_obj.read()
                file_size = len(file_content)
                # Validate file size
                max_size = self.get_max_file_size()
                if file_size > max_size:
                    max_size_mb = max_size / (1024 * 1024)
                    return {
                        'success': False,
                        'error': f'File size ({file_size / (1024 * 1024):.2f} MB) exceeds maximum allowed size ({max_size_mb} MB).'
                    }
                content_type = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type,
                ACL='public-read'  # Make file publicly accessible
            )
            
            # Build S3 URL
            s3_url = urljoin(self.s3_base_url.rstrip('/') + '/', s3_key)
            
            # Save to database
            s3_upload = S3FileUpload.objects.create(
                file_name=file_name,
                s3_key=s3_key,
                s3_url=s3_url,
                file_type=content_type,
                file_size=file_size,
                folder_path=folder_path if folder_path else None,
                description=description,
                uploaded_by=uploaded_by
            )
            
            return {
                'success': True,
                's3_url': s3_url,
                's3_key': s3_key,
                'file_size': file_size,
                'content_type': content_type,
                'upload_id': s3_upload.id
            }
            
        except NoCredentialsError:
            return {
                'success': False,
                'error': 'AWS credentials not found. Please configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.'
            }
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            return {
                'success': False,
                'error': f'AWS S3 Error ({error_code}): {error_message}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Upload failed: {str(e)}'
            }
    
    def delete_file(self, s3_key):
        """
        Delete a file from S3 bucket (only files, not folders)
        
        Args:
            s3_key: S3 object key/path to delete
        
        Returns:
            dict with 'success' (bool) and 'error' (str)
        """
        if not self.s3_client:
            return {
                'success': False,
                'error': 'S3 client not initialized.'
            }
        
        # Prevent deletion of folders (keys ending with /)
        if s3_key.endswith('/'):
            return {
                'success': False,
                'error': 'Cannot delete folder. Only individual files can be deleted.'
            }
        
        try:
            # Verify it's a file (not a folder) by checking if it exists and has content
            try:
                response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
                # If it exists, proceed with deletion
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    return {
                        'success': False,
                        'error': 'File not found in S3 bucket.'
                    }
                raise
            
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            
            # Delete from database
            S3FileUpload.objects.filter(s3_key=s3_key).delete()
            
            return {'success': True}
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            return {
                'success': False,
                'error': f'AWS S3 Error ({error_code}): {error_message}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Delete failed: {str(e)}'
            }
    
    def list_files(self, folder_path='', prefix=''):
        """
        List files in S3 bucket
        
        Args:
            folder_path: Optional folder path to filter
            prefix: Optional prefix to filter files
        
        Returns:
            list of file objects
        """
        if not self.s3_client:
            return []
        
        try:
            prefix_to_use = folder_path if folder_path else prefix
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix_to_use
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'url': urljoin(self.s3_base_url.rstrip('/') + '/', obj['Key'])
                    })
            
            return files
        except Exception as e:
            print(f"Error listing S3 files: {e}")
            return []
    
    def list_folders_and_files(self, folder_path=''):
        """
        List folders and files in S3 bucket (FTP-like structure)
        
        Args:
            folder_path: Optional folder path to browse
        
        Returns:
            dict with 'folders' (list) and 'files' (list)
        """
        if not self.s3_client:
            return {'folders': [], 'files': []}
        
        try:
            # Normalize folder path
            if folder_path:
                folder_path = folder_path.strip('/')
                if not folder_path.endswith('/'):
                    folder_path += '/'
            else:
                folder_path = ''
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=folder_path,
                Delimiter='/'
            )
            
            folders = []
            files = []
            
            # Get folders (CommonPrefixes)
            if 'CommonPrefixes' in response:
                for prefix in response['CommonPrefixes']:
                    folder_name = prefix['Prefix'].replace(folder_path, '').rstrip('/')
                    folders.append({
                        'name': folder_name,
                        'path': prefix['Prefix'].rstrip('/')
                    })
            
            # Get files
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Skip the folder marker itself
                    if obj['Key'] == folder_path or obj['Key'].endswith('/'):
                        continue
                    
                    file_name = obj['Key'].replace(folder_path, '')
                    # Skip if it's in a subfolder (contains /)
                    if '/' in file_name:
                        continue
                    
                    # Get file info from database if available
                    db_file = S3FileUpload.objects.filter(s3_key=obj['Key']).first()
                    
                    files.append({
                        'key': obj['Key'],
                        'name': file_name,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'url': urljoin(self.s3_base_url.rstrip('/') + '/', obj['Key']),
                        'file_type': db_file.file_type if db_file else mimetypes.guess_type(file_name)[0] or 'application/octet-stream',
                        'id': db_file.id if db_file else None
                    })
            
            return {'folders': folders, 'files': files}
        except Exception as e:
            print(f"Error listing S3 folders and files: {e}")
            return {'folders': [], 'files': []}
    
    def create_folder(self, folder_path):
        """
        Create a folder in S3 (creates a placeholder object)
        
        Args:
            folder_path: Folder path to create (e.g., 'media/images', 'ebook')
        
        Returns:
            dict with 'success' (bool) and 'error' (str)
        """
        if not self.s3_client:
            return {
                'success': False,
                'error': 'S3 client not initialized.'
            }
        
        try:
            # Normalize folder path
            folder_path = folder_path.strip('/')
            if not folder_path.endswith('/'):
                folder_path += '/'
            
            # Check if folder already exists
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=folder_path,
                MaxKeys=1
            )
            
            if 'Contents' in response and len(response['Contents']) > 0:
                return {
                    'success': False,
                    'error': 'Folder already exists or contains files.'
                }
            
            # Create folder marker (empty object with trailing slash)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=folder_path,
                Body=b'',
                ContentType='application/x-directory'
            )
            
            return {'success': True}
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            return {
                'success': False,
                'error': f'AWS S3 Error ({error_code}): {error_message}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Create folder failed: {str(e)}'
            }
    
    def object_exists(self, s3_key):
        """Check if an S3 object exists. Returns True if exists, False if NoSuchKey or error."""
        if not self.s3_client:
            return False
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == '404':
                return False
            raise
        except Exception:
            return False

    def generate_presigned_url(self, s3_key, expires_in=3600):
        """
        Generate a presigned URL for temporary access to a private S3 object.
        
        Args:
            s3_key: S3 object key (path in bucket)
            expires_in: URL expiry in seconds (default 1 hour)
        
        Returns:
            str: Presigned URL or None on error
        """
        if not self.s3_client:
            return None
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            print(f"Error generating presigned URL for {s3_key}: {e}")
            return None

    def s3_key_from_url(self, url):
        """
        Extract S3 object key from a full S3 URL.
        E.g. https://bucket.s3.region.amazonaws.com/path/to/file.pdf -> path/to/file.pdf
        """
        if not url:
            return None
        from urllib.parse import urlparse, unquote
        base = getattr(settings, 'S3_BUCKET_BASE_URL', '').rstrip('/') + '/'
        if url.startswith(base):
            key = url[len(base):].lstrip('/')
            return unquote(key) if key else None
        # Try parsing generic S3 URL format (path is the key)
        parsed = urlparse(url)
        path = parsed.path.lstrip('/')
        return unquote(path) if path else None

    def delete_folder(self, folder_path):
        """
        Delete a folder from S3 (deletes all objects with the prefix)
        
        Args:
            folder_path: Folder path to delete
        
        Returns:
            dict with 'success' (bool) and 'error' (str)
        """
        if not self.s3_client:
            return {
                'success': False,
                'error': 'S3 client not initialized.'
            }
        
        try:
            # Normalize folder path
            folder_path = folder_path.strip('/')
            if not folder_path.endswith('/'):
                folder_path += '/'
            
            # List all objects in the folder
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=folder_path
            )
            
            if 'Contents' not in response or len(response['Contents']) == 0:
                return {
                    'success': False,
                    'error': 'Folder is empty or does not exist.'
                }
            
            # Delete all objects in the folder
            objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
            
            if objects_to_delete:
                # Delete in batches of 1000 (S3 limit)
                for i in range(0, len(objects_to_delete), 1000):
                    batch = objects_to_delete[i:i+1000]
                    self.s3_client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={'Objects': batch}
                    )
            
            # Delete database records
            S3FileUpload.objects.filter(s3_key__startswith=folder_path).delete()
            
            return {'success': True}
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            return {
                'success': False,
                'error': f'AWS S3 Error ({error_code}): {error_message}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Delete folder failed: {str(e)}'
            }


def get_s3_upload_service():
    """Get an instance of S3UploadService"""
    return S3UploadService()
