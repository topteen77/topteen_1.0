var checkoutcourse = document.querySelectorAll(".checkoutcourse");
checkoutcourse.forEach(elm=>{
    if(elm){elm.onclick = function(e){
        var course_slug= $(this).data('course-slug');
        createOrder(course_slug);
        e.preventDefault();
    }}
})



function createOrder(course_slug){
    var formData = new FormData();
    formData.append("skilllabcourse",course_slug);
    $.ajax({
        url: create_skillabcourse_payment,
        type: 'POST',
        data: formData,
        success: function (data) {
            try{
                    openRazorpay(data);
            }
            catch(err) {
                console.log(err);
                fireAlert("Internal Server Error","error");
            }
        },
        error: function (xhr, ajaxOptions, thrownError) {
            if(xhr.status==403) {
                fireAlert("You must be logged in, proceed?","error");
            }
            if(xhr.status==400) {
                fireAlert("The payment cannot process at the moment.","error");
            }
          },
        cache: false,
        contentType: false,
        processData: false
    });
}

function updatePayment(sp_id,pay_id,response,success_url,fail_url){
    var data = {gateway_order_id:response.razorpay_order_id,gateway_payment_id:response.razorpay_payment_id,gateway_signature:response.razorpay_signature,sp_id:sp_id,payment_id:pay_id};
    $.ajax({
        url: update_skillabcourse_payment,
        headers: { 
            'Accept': 'application/json',
            'Content-Type': 'application/json' 
        },
        type: 'POST',
        data:JSON.stringify(data),
        success: function (data) {
            window.location.href = success_url
        },
        error: function(data){
            window.location.href = fail_url
          },
        cache: false,
        contentType: false,
        processData: false
    });
  }


function openRazorpay(data){    
        data.payment_info["handler"] = function (response){
            updatePayment(data.sp_id,data.pay_id,response,data.success_url,data.fail_url);
        }
        data.payment_info["modal"] = {
                "ondismiss": function(){
                    window.location.href = data.fail_url                   
                }
        }
    var rzp1 = new Razorpay(data.payment_info);
    rzp1.open();
    rzp1.on('payment.failed', function (response){
        fireAlert(response.error.code,"error");
        fireAlert(response.error.description,"error");
        // alert(response.error.source);
        // alert(response.error.step);
        // alert(response.error.reason);
        // alert(response.error.metadata.order_id);
        // alert(response.error.metadata.payment_id);
        // alert(response.error.metadata);
    });
}