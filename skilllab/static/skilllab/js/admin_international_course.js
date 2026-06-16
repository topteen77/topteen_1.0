(function () {
    function bindFilePreview(inputId, previewId) {
        var input = document.getElementById(inputId);
        var preview = document.getElementById(previewId);
        if (!input || !preview) {
            return;
        }

        input.addEventListener("change", function (event) {
            var file = event.target.files && event.target.files[0];
            if (!file) {
                return;
            }
            var reader = new FileReader();
            reader.onload = function (loadEvent) {
                preview.src = loadEvent.target.result;
            };
            reader.readAsDataURL(file);
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        bindFilePreview("id_image", "intl-course-image-preview");
        bindFilePreview("id_logo", "intl-course-logo-preview");
    });
})();
