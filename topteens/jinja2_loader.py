"""
Custom Jinja2 loader that skips admin templates to allow Django admin to use Django templates.
"""
from jinja2 import FileSystemLoader, TemplateNotFound, ChoiceLoader
from django.conf import settings
from django.template.loaders.app_directories import get_app_template_dirs
import os


class AdminAwareFileSystemLoader(FileSystemLoader):
    """
    Custom FileSystemLoader that skips admin templates.
    This allows Django admin to use Django templates while frontend uses Jinja2.
    """
    
    def get_source(self, environment, template):
        # Skip admin templates - let Django templates handle them
        # Check for admin/ prefix at the start of template name
        if template.startswith('admin/'):
            raise TemplateNotFound(template)
        
        # For all other templates, use the parent loader
        return super().get_source(environment, template)


class AdminAwareAppLoader(FileSystemLoader):
    """
    Custom app loader that skips admin templates from app directories.
    Uses FileSystemLoader to search app template directories but skips admin templates.
    """
    
    def get_source(self, environment, template):
        # Skip admin templates - let Django templates handle them
        if template.startswith('admin/'):
            raise TemplateNotFound(template)
        
        # For all other templates, use the parent loader
        try:
            return super().get_source(environment, template)
        except TemplateNotFound:
            raise


def get_jinja2_loader():
    """
    Create a Jinja2 loader that skips admin templates.
    Combines FileSystemLoader for DIRS and app directories, both skipping admin templates.
    """
    loaders = []
    
    # Get directories from Jinja2 template config
    jinja2_config = None
    for template_config in settings.TEMPLATES:
        if template_config['BACKEND'] == 'django.template.backends.jinja2.Jinja2':
            jinja2_config = template_config
            break
    
    # Add FileSystemLoader for DIRS
    if jinja2_config and 'DIRS' in jinja2_config:
        template_dirs = []
        for dir_path in jinja2_config['DIRS']:
            if isinstance(dir_path, str):
                # Handle relative paths
                if not os.path.isabs(dir_path):
                    dir_path = os.path.join(settings.BASE_DIR, dir_path)
                if os.path.exists(dir_path):
                    template_dirs.append(dir_path)
            else:
                template_dirs.append(str(dir_path))
        
        if template_dirs:
            loaders.append(AdminAwareFileSystemLoader(template_dirs))
    
    # Always add app directories loader (we handle it manually to skip admin templates)
    # This ensures app templates are available but admin templates are skipped
    app_dirs = get_app_template_dirs('templates')
    if app_dirs:
        loaders.append(AdminAwareAppLoader(app_dirs))
    
    # Return a ChoiceLoader that tries each loader in order
    if len(loaders) == 1:
        return loaders[0]
    elif len(loaders) > 1:
        return ChoiceLoader(loaders)
    else:
        # Fallback to empty loader
        return AdminAwareFileSystemLoader([])

