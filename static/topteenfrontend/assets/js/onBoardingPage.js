$(document).ready(function () {
    $(".newPages").slick({
        dots: true,
        speed: 300,
        slidesToShow: 1,
        centerMode: true,
        variableWidth: true,
        adaptiveHeight: true,
        infinite:false,
        // adaptiveWidth: true,
        responsive: [
            {
                breakpoint: 375,
                settings: {
                    dots: true,
                    speed: 300,
                    slidesToShow: 1,
                    adaptiveHeight: true,
                    centerMode: true,
                    variableWidth: true,
                    adaptiveHeight: true,

                }
            },
        ]
    });

    $('.newPages .slick-dots li button').on('click', function(e){
        e.stopPropagation(); // use this
    });

    //Sliding function for a button click

    const newFunc = function(ele){
        var formName=$(ele).data('form-name')
        if (formName=="firstform"){
            return validatefigureoutform();
        }
        if (formName=="secondform"){
            return validateuserinfoform();
        }
        if (formName=="thirdform"){
            return validatesubjectform();
        }
        return true
    }

     var indexVal=1;  
        $(".slideOnButton").click(function(e){
        const funcVal = newFunc(this)
        e.preventDefault();
            if(funcVal){
                // slideIndex = $(this).index();
                $( '.newPages' ).slick('slickGoTo', indexVal);
                indexVal=indexVal+1;
                if(indexVal>5){
                indexVal=1;
                } 
            }else {

            }
 });

    //End of sliding function for a button click
});

function validatefigureoutform(){
    var checkedf=$('input[name="userfigureout"]:checked').length;
    if(!checkedf){
        fireAlert("Please select atleast one", "error");
        return false
    }
    return true
}

function validatesubjectform(){
    var checkedf=$('input[name="usersubject"]:checked').length;
    if(!checkedf){
        fireAlert("Please select atleast one subject", "error");
        return false
    }
    return true
}

function validatehobbiesform(){
    var checkedf=$('input[name="hobbies"]:checked').length;
    if(!checkedf){
        
        fireAlert("Please select atleast one hobbies", "error");
        return false
    }
    return true
}

function validateuserinfoform(){

    if ($('input[name="username"]').val()==""){
        fireAlert("Please enter a name", "error")
        return false
    }
    if ($('input[name="userbirthdaydate"]').val()==""){
        fireAlert("Please enter a birth date","error")
        return false
    }
    if (document.getElementById('gender').value==""){
        fireAlert("Please select a gender","error")
        return false
    }
    if ($('input[name="userphone"]').val()=="" || !validatepPhone($('input[name="userphone"]').val())){
        fireAlert("Please enter a valid phone number","error")
        return false
    }
    if ($('input[name="userschool"]').val()==""){
        fireAlert("Please enter a school","error")
        return false
    }
    if ($('input[name="usergrade"]').val()==""){
        fireAlert("Please enter a grade","error")
        return false
    }
    return true
}



function validatepPhone(phone) {
  if (
    phone.match(/^\d*(?:\.\d{1,2})?$/) &&  phone.length == 10
  ) {
    return true;
  } else {
    return false;
  }
}

$(".subDiv").click(function(){
    $(this).toggleClass("selectedDiv activeTab");
})

const imgBtn = document.querySelector(".imgBtn");
const imgIp = document.querySelector(".imgIp");

imgBtn.addEventListener("click", function(){
    imgIp.click();
})

imgIp.addEventListener("change", function(e){
    console.log(e.target.files);
    const file = e.target.files[0];
    const url = URL.createObjectURL(file)
    imgBtn.querySelector("img").src = url;
})

// For tab key press

$('body').on('keydown', 'input, select', function(e) {
    if (e.key === "Tab") {
        var self = $(this), form = self.parents('form:eq(0)'), focusable, next;
        focusable = form.find('input,a,select,button,textarea').filter(':visible');
        next = focusable.eq(focusable.index(this)+1);
        if (next.length) {
            next.focus();
        } else {
            form.submit();
        }
        return false;
    }
});