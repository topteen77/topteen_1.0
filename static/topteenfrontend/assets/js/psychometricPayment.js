var checkoutbasic = document.getElementById('checkoutbasic');
if(checkoutbasic){checkoutbasic.onclick = function(e){
    var test_type= $(this).data('test-type');
    createOrder(test_type);
    e.preventDefault();
}}

var checkoutadvanced = document.getElementById('checkoutadvanced');
if(checkoutadvanced){checkoutadvanced.onclick = function(e){
    var test_type= $(this).data('test-type');
    createOrder(test_type);
    e.preventDefault();
}}

function createOrder(test_type){
    var formData = new FormData();
    formData.append("test_type",test_type);
    $.ajax({
        url: create_pyschometric_payment,
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
        error: function(data){
            try{
                fireAlert(data.responseJSON.message,"error");
            }
            catch(e){
                fireAlert("Internal Server Error","error");
            }
            },
        cache: false,
        contentType: false,
        processData: false
    });
}

function updatePayment(test_id,pay_id,test_type,response,success_url,fail_url){
    var data = {gateway_order_id:response.razorpay_order_id,gateway_payment_id:response.razorpay_payment_id,gateway_signature:response.razorpay_signature,test_id:test_id,payment_id:pay_id,test_type:test_type};
    $.ajax({
        url: update_pyschometric_payment,
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

function createCentralTest(test_id,test_type){
    var data = {test_id:test_id,test_type:test_type};
    $.ajax({
        url: create_central_test,
        headers: { 
            'Accept': 'application/json',
            'Content-Type': 'application/json' 
        },
        type: 'POST',
        data:JSON.stringify(data),
        success: function (data) {
              alert(data);
              window.location.reload();  
        },
        error: function(data){
            alert("Internal Server error");
          },
        cache: false,
        contentType: false,
        processData: false
    });
  }

function openRazorpay(data){    
        data.payment_info["handler"] = function (response){
            updatePayment(data.test_id,data.pay_id,data.test_type,response,data.success_url,data.fail_url);
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