function loginsingup() {
  let phoneEmail = document.getElementById("mobileEmail").value;
  if (validateLoginSignup(phoneEmail) == false) {
    document.getElementById("errorMsgSinguplogin").innerHTML =
      "Please enter valid email ";
    return false;
  }
  var formData = new FormData();
  formData.append("user_name", phoneEmail);
  console.log("formData",formData)
  
  $.ajax({
    type: "POST",
    url: usersloginsignup,
    data: formData,
    
    success: function (data) {
      if (data.show_otp) {
        loginsingupremoveunusetag();
        var x = document.createElement("input");
        x.setAttribute("type", "hidden");
        x.setAttribute("value", data.user_name);
        x.setAttribute("id", "signupusername");
        x.setAttribute("name", "user_name");
        document.getElementById("singupotp").appendChild(x);
        document.getElementById("signupotpname").textContent = data.user_name;
        document.getElementById("otpDiv").classList.remove("hideModal");
        
        // Auto-focus on first OTP input when modal is shown
        setTimeout(function() {
          const firstOtpInput = document.querySelector('.otpSource');
          if (firstOtpInput) {
            firstOtpInput.focus();
          }
        }, 100);
      }
      if (data.show_password) {
        loginremoveunusetag();
        var x = document.createElement("input");
        x.setAttribute("type", "hidden");
        x.setAttribute("value", data.enc_user_name);
        x.setAttribute("id", "encloginusername");
        x.setAttribute("name", "enc_user_name");
        document.getElementById("loginpwd").appendChild(x);
        document.getElementById("loginpwdname").textContent = data.user_name;
        document.getElementById("loginpwdDiv").classList.remove("hideModal");
        
        // Auto-focus on password input when modal is shown
        setTimeout(function() {
          const passwordInput = document.querySelector('#loginpwd input[name="password"]');
          if (passwordInput) {
            passwordInput.focus();
          }
        }, 100);
      }
    },
    error: function (xhr, status, error) {
      try {
        if (xhr.status === 403) {
          // Don't show message, just redirect silently
          setTimeout(function() {
            window.location.href = '/user/login';
          }, 100);
        } else if (xhr.status === 400) {
          fireAlert("Invalid request. Please check your input and try again", "error");
        } else if (xhr.status === 401) {
          fireAlert("Authentication failed. Please check your credentials", "error");
        } else if (xhr.status === 500) {
          fireAlert("Server error. Please try again later", "error");
        } else if (xhr.status === 0) {
          fireAlert("Network error. Please check your connection", "error");
        } else {
          fireAlert("Something went wrong. Please try again", "error");
        }
      } catch (e) {
        fireAlert("An unexpected error occurred. Please try again", "error");
      }
    },
    cache: false,
    contentType: false,
    processData: false,
  });
  return false;
}

function loginremoveunusetag() {
  if ($("#encloginusername").length) {
    $("#encloginusername").remove();
  }
  document.getElementById("errorMsgloginpwd").innerHTML = "";
}

function loginsingupremoveunusetag() {
  if ($("#signupusername").length) {
    $("#signupusername").remove();
  }
  document.getElementById("errorMsgSinguplogin").innerHTML = "";
}

function validateLoginSignup(phoneEmail) {
  if (phoneEmail == "") {
    return false;
  }
  if (validateEmail(phoneEmail)) {
    return true;
  }
  return false;
}

function validateEmail(phoneEmail) {
  if (
    phoneEmail.match(
      /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/
    )
  ) {
    return true;
  } else {
    return false;
  }
}

// function validatepPhone(phoneEmail) {
//   if (
//     phoneEmail.match(/^\+?([0-9]{2})\)?([0-9]{3})\)?([0-9]{3})?([0-9]{4})$/)
//   ) {
//     return true;
//   } else {
//     return false;
//   }
// }

function loginsingupotp() {
  var formData = new FormData(document.getElementById("singupotp"));
  if (validateotp(formData) == false) {
    return false;
  }
  $.ajax({
    type: "POST",
    url: userssignupotpverify,
    data: formData,
    success: function (data) {
      if (data.otp_verify != true) {
        var otperrtag = document.getElementById("errorMsgOtpSinguplogin");
        otperrtag.textContent = "The otp you entered is incorrect. Try Again";
      }

      if (data.otp_verify == true) {
        // Check if user already exists (returning user)
        if (data.user_exists === true && data.success === true) {
          // User exists and is logged in - redirect to dashboard
          loginsingupotpremoveunusetag();
          if (data.redirect_url) {
            window.location.href = data.redirect_url;
          } else {
            window.location.href = '/user/dashboard';
          }
        } else {
          // New user (user_exists is false or undefined) - proceed to password form
          // This handles both explicit false and cases where user_exists might be undefined
          if (data.enc_user_name) {
            loginsingupotpremoveunusetag();
            
            // Remove any existing enc_user_name input
            var existingInput = document.getElementById("encsignupusername");
            if (existingInput) {
              existingInput.remove();
            }
            
            // Add encrypted username to password form
            var x = document.createElement("input");
            x.setAttribute("type", "hidden");
            x.setAttribute("value", data.enc_user_name);
            x.setAttribute("id", "encsignupusername");
            x.setAttribute("name", "enc_user_name");
            
            var signupPwdForm = document.getElementById("singuppwd");
            if (signupPwdForm) {
              signupPwdForm.appendChild(x);
            } else {
              console.error("Signup password form not found!");
            }
            
            // Update email display
            var signupPwdName = document.getElementById("signuppwdname");
            if (signupPwdName && data.user_name) {
              signupPwdName.textContent = data.user_name;
            }
            
            // Show password modal
            var signUpPwdDiv = document.getElementById("signUpPwdDiv");
            if (signUpPwdDiv) {
              signUpPwdDiv.classList.remove("hideModal");
              
              // Auto-select class based on sessionStorage
              setTimeout(function() {
                const classDropdown = document.getElementById("signupGrade");
                if (classDropdown) {
                  // Check sessionStorage for signup_class
                  const signupClass = sessionStorage.getItem('signup_class');
                  if (signupClass === '10' || signupClass === '12') {
                    classDropdown.value = signupClass;
                    // Clear sessionStorage after use
                    sessionStorage.removeItem('signup_class');
                  } else {
                    // Default to class 10 if not set
                    classDropdown.value = '10';
                  }
                  classDropdown.focus();
                }
              }, 200);
            } else {
              console.error("Signup password modal div not found!");
            }
          } else {
            console.error("No enc_user_name in response for new user signup");
            var otperrtag = document.getElementById("errorMsgOtpSinguplogin");
            if (otperrtag) {
              otperrtag.textContent = "Error: Missing user information. Please try again.";
            }
          }
        }
      }
    },
    error: function (xhr, status, error) {
      try {
        if (xhr.status === 403) {
          // Don't show message, just redirect silently
          setTimeout(function() {
            window.location.href = '/user/login';
          }, 100);
        } else if (xhr.status === 400) {
          fireAlert("Invalid request. Please check your input and try again", "error");
        } else if (xhr.status === 401) {
          fireAlert("Authentication failed. Please check your credentials", "error");
        } else if (xhr.status === 500) {
          fireAlert("Server error. Please try again later", "error");
        } else if (xhr.status === 0) {
          fireAlert("Network error. Please check your connection", "error");
        } else {
          fireAlert("Something went wrong. Please try again", "error");
        }
      } catch (e) {
        fireAlert("An unexpected error occurred. Please try again", "error");
      }
    },
    cache: false,
    contentType: false,
    processData: false,
  });
  return false;
}

function loginsingupotpremoveunusetag() {
  if ($("#signupusername").length) {
    $("#signupusername").remove();
  }
  document.getElementById("singupotp").reset();
  document.getElementById("errorMsgOtpSinguplogin").innerHTML = "";
  document.getElementById("otpDiv").classList.add("hideModal");
}

function validateotp(formData) {
  if (
    formData.getAll("otp").filter((el) => {
      return el;
    }).length != 6
  ) {
    var otperrtag = document.getElementById("errorMsgOtpSinguplogin");
    otperrtag.textContent = "All fields required. Try Again";
    return false;
  }
  return true;
}

function loginsinguppwd() {
  var formData = new FormData(document.getElementById("singuppwd"));
  if (validatepwd(formData) == false) {
    return false;
  }
  
  // Clear any previous error messages
  var otperrtag = document.getElementById("errorMsgOtpSinguploginpwd");
  if (otperrtag) {
    otperrtag.textContent = "";
  }
  
  $.ajax({
    type: "POST",
    url: usersloginsignuppwd,
    data: formData,
    success: async function (data) {
      if (data.success) {
        // Account created successfully
        await fireAlert("Account created successfully", "success");
        setTimeout(() => {
          if (data.redirect_url) {
            window.location.href = data.redirect_url;
          } else {
            window.location.href = '/user/dashboard';
          }
        }, 1000);
      } else {
        // Show error message from server
        var otperrtag = document.getElementById("errorMsgOtpSinguploginpwd");
        if (otperrtag && data.message) {
          otperrtag.textContent = data.message;
        } else if (otperrtag) {
          otperrtag.textContent = "Something went wrong. Please try again.";
        }
      }
    },
    error: function (xhr, status, error) {
      try {
        // Try to parse error response
        var errorMessage = "Something went wrong. Please try again.";
        if (xhr.responseJSON && xhr.responseJSON.message) {
          errorMessage = xhr.responseJSON.message;
        } else if (xhr.responseText) {
          try {
            var errorData = JSON.parse(xhr.responseText);
            if (errorData.message) {
              errorMessage = errorData.message;
            }
          } catch (e) {
            // If parsing fails, use default message
          }
        }
        
        // Show error in the password form error message area
        var otperrtag = document.getElementById("errorMsgOtpSinguploginpwd");
        if (otperrtag) {
          otperrtag.textContent = errorMessage;
        }
        
        if (xhr.status === 403) {
          // Don't show message, just redirect silently
          setTimeout(function() {
            window.location.href = '/user/login';
          }, 100);
        } else if (xhr.status === 400) {
          // Error message already shown above
          fireAlert(errorMessage, "error");
        } else if (xhr.status === 401) {
          fireAlert("Authentication failed. Please check your credentials", "error");
        } else if (xhr.status === 500) {
          fireAlert("Server error. Please try again later", "error");
        } else if (xhr.status === 0) {
          fireAlert("Network error. Please check your connection", "error");
        } else {
          fireAlert(errorMessage, "error");
        }
      } catch (e) {
        fireAlert("An unexpected error occurred. Please try again", "error");
      }
    },
    cache: false,
    contentType: false,
    processData: false,
  });
  return false;
}

function validatepwd(formData) {
  // Validate class/grade selection
  var grade = formData.get("grade");
  if (!grade || grade === "") {
    var otperrtag = document.getElementById("errorMsgOtpSinguploginpwd");
    otperrtag.textContent = "Please select your class. Try Again";
    return false;
  }
  
  // Validate password
  if (formData.get("password") == "") {
    var otperrtag = document.getElementById("errorMsgOtpSinguploginpwd");
    otperrtag.textContent = "All fields required. Try Again";
    return false;
  }
  
  // Validate password match
  if (formData.get("password") != formData.get("confirm_password")) {
    var otperrtag = document.getElementById("errorMsgOtpSinguploginpwd");
    otperrtag.textContent = "Password does not match. Try Again";
    return false;
  }
  return true;
}

function loginpwd() {
  var formData = new FormData(document.getElementById("loginpwd"));
  if (validateloginpwd(formData) == false) {
    return false;
  }
  $.ajax({
    type: "POST",
    url: usersloginpwd,
    data: formData,
    success: function (data) {
      if (data.success) {
        document.getElementById("loginpwdDiv").classList.add("hideModal");
        window.location.href = data.redirect_url;
      }
      if (data.success == false) {
        var otperrtag = document.getElementById("errorMsgloginpwd");
        otperrtag.textContent = data.errMsg;
      }
    },
    error: function (xhr, status, error) {
      try {
        if (xhr.status === 403) {
          // Don't show message, just redirect silently
          setTimeout(function() {
            window.location.href = '/user/login';
          }, 100);
        } else if (xhr.status === 400) {
          fireAlert("Invalid request. Please check your input and try again", "error");
        } else if (xhr.status === 401) {
          fireAlert("Authentication failed. Please check your credentials", "error");
        } else if (xhr.status === 500) {
          fireAlert("Server error. Please try again later", "error");
        } else if (xhr.status === 0) {
          fireAlert("Network error. Please check your connection", "error");
        } else {
          fireAlert("Something went wrong. Please try again", "error");
        }
      } catch (e) {
        fireAlert("An unexpected error occurred. Please try again", "error");
      }
    },
    cache: false,
    contentType: false,
    processData: false,
  });
  return false;
}

function validateloginpwd(formData) {
  if (formData.get("password") == "") {
    var otperrtag = document.getElementById("errorMsgloginpwd");
    otperrtag.textContent = "All fields required. Try Again";
    return false;
  }
}

function forgotpasswordshow() {
  document.getElementById("loginpwdDiv").classList.add("hideModal");
  document.getElementById("forgotDiv").classList.remove("hideModal");
}

function forgotpassword() {
  let phoneEmail = document.getElementById("forgotmobileEmail").value;
  if (validateLoginSignup(phoneEmail) == false) {
    document.getElementById("errorMsgforgot").innerHTML =
      "Please enter valid email";
    return false;
  }
  var formData = new FormData();
  formData.append("user_name", phoneEmail);
  $.ajax({
    type: "POST",
    url: usersforgotpassword,
    data: formData,
    success: function (data) {
      if (data.success) {
        forgotpwdremoveunusetag();
        var x = document.createElement("input");
        x.setAttribute("type", "hidden");
        x.setAttribute("value", data.enc_user_name);
        x.setAttribute("id", "forgotpwdusername");
        x.setAttribute("name", "user_name");
        document.getElementById("forgototppwd").appendChild(x);
        document.getElementById("forgototppwdname").textContent =
          data.user_name;
        document
          .getElementById("forgotpwdotpDiv")
          .classList.remove("hideModal");
      }
      if (data.success == false) {
        document.getElementById("errorMsgforgot").textContent = data.message;
        document.getElementById("forgotpwdname").textContent = data.user_name;
      }
    },
    error: function (xhr, status, error) {
      try {
        if (xhr.status === 403) {
          // Don't show message, just redirect silently
          setTimeout(function() {
            window.location.href = '/user/login';
          }, 100);
        } else if (xhr.status === 400) {
          fireAlert("Invalid request. Please check your input and try again", "error");
        } else if (xhr.status === 401) {
          fireAlert("Authentication failed. Please check your credentials", "error");
        } else if (xhr.status === 500) {
          fireAlert("Server error. Please try again later", "error");
        } else if (xhr.status === 0) {
          fireAlert("Network error. Please check your connection", "error");
        } else {
          fireAlert("Something went wrong. Please try again", "error");
        }
      } catch (e) {
        fireAlert("An unexpected error occurred. Please try again", "error");
      }
    },
    cache: false,
    contentType: false,
    processData: false,
  });
  return false;
}

function forgotpwdremoveunusetag() {
  document.getElementById("errorMsgforgot").innerHTML = "";
  document.getElementById("forgotpwdform").reset();
  document.getElementById("forgotDiv").classList.add("hideModal");
}

function forgotpasswordotp() {
  var formData = new FormData(document.getElementById("forgototppwd"));
  if (validatepwdotp(formData) == false) {
    return false;
  }
  $.ajax({
    type: "POST",
    url: usersforgotpasswordotp,
    data: formData,
    success: function (data) {
      if (data.success != true) {
        var otperrtag = document.getElementById("errorMsgfotgototp");
        otperrtag.textContent = "The otp you entered is incorrect. Try Again";
      }
      if (data.success == true) {
        document.getElementById("forgotpwdotpDiv").classList.add("hideModal");
        document
          .getElementById("successotpPopUp")
          .classList.remove("hideModal");
      }
    },
    error: function (xhr, status, error) {
      try {
        if (xhr.status === 403) {
          // Don't show message, just redirect silently
          setTimeout(function() {
            window.location.href = '/user/login';
          }, 100);
        } else if (xhr.status === 400) {
          fireAlert("Invalid request. Please check your input and try again", "error");
        } else if (xhr.status === 401) {
          fireAlert("Authentication failed. Please check your credentials", "error");
        } else if (xhr.status === 500) {
          fireAlert("Server error. Please try again later", "error");
        } else if (xhr.status === 0) {
          fireAlert("Network error. Please check your connection", "error");
        } else {
          fireAlert("Something went wrong. Please try again", "error");
        }
      } catch (e) {
        fireAlert("An unexpected error occurred. Please try again", "error");
      }
    },
    cache: false,
    contentType: false,
    processData: false,
  });
  return false;
}

function validatepwdotp(formData) {
  if (
    formData.getAll("otp").filter((el) => {
      return el;
    }).length != 6
  ) {
    var otperrtag = document.getElementById("errorMsgfotgototp");
    otperrtag.textContent = "All fields required. Try Again";
    return false;
  }
  if (formData.get("password") == "") {
    var otperrtag = document.getElementById("errorMsgfotgototp");
    otperrtag.textContent = "All fields required. Try Again";
    return false;
  }
  if (formData.get("password") != formData.get("confirm_password")) {
    var otperrtag = document.getElementById("errorMsgfotgototp");
    otperrtag.textContent = "Password does not match. Try Again";
    return false;
  }
  return true;
}

function reSendForgotOtp() {
  var formData = new FormData();
  var usernameInput = document.getElementById("forgotpwdusername");
  if (usernameInput) {
    formData.append("user_name", usernameInput.value);
  } else {
    // Try to get from the form
    var forgotForm = document.getElementById("forgototppwd");
    if (forgotForm) {
      var hiddenInput = forgotForm.querySelector('input[name="user_name"]');
      if (hiddenInput) {
        formData.append("user_name", hiddenInput.value);
      }
    }
  }
  
  if (!formData.get("user_name")) {
    fireAlert("Unable to resend OTP. Please try again.", "error");
    return false;
  }
  
  $.ajax({
    type: "POST",
    url: usersresendotp,
    data: formData,
    success: function (data) {
      fireAlert("OTP sent successfully", "success");
    },
    error: function (xhr, status, error) {
      try {
        if (xhr.status === 403) {
          setTimeout(function() {
            window.location.href = '/user/login';
          }, 100);
        } else if (xhr.status === 400) {
          fireAlert("Invalid request. Please check your input and try again", "error");
        } else if (xhr.status === 401) {
          fireAlert("Authentication failed. Please check your credentials", "error");
        } else if (xhr.status === 500) {
          fireAlert("Server error. Please try again later", "error");
        } else if (xhr.status === 0) {
          fireAlert("Network error. Please check your connection", "error");
        } else {
          fireAlert("Something went wrong. Please try again", "error");
        }
      } catch (e) {
        fireAlert("An unexpected error occurred. Please try again", "error");
      }
    },
    cache: false,
    contentType: false,
    processData: false,
  });
  return false;
}

function reSendOtp() {
  var formData = new FormData(document.getElementById("singupotp"));
  $.ajax({
    type: "POST",
    url: usersresendotp,
    data: formData,
    success: function (data) {
      fireAlert("Otp sent successfully", "success");
    },
    error: function (xhr, status, error) {
      try {
        if (xhr.status === 403) {
          // Don't show message, just redirect silently
          setTimeout(function() {
            window.location.href = '/user/login';
          }, 100);
        } else if (xhr.status === 400) {
          fireAlert("Invalid request. Please check your input and try again", "error");
        } else if (xhr.status === 401) {
          fireAlert("Authentication failed. Please check your credentials", "error");
        } else if (xhr.status === 500) {
          fireAlert("Server error. Please try again later", "error");
        } else if (xhr.status === 0) {
          fireAlert("Network error. Please check your connection", "error");
        } else {
          fireAlert("Something went wrong. Please try again", "error");
        }
      } catch (e) {
        fireAlert("An unexpected error occurred. Please try again", "error");
      }
    },
    cache: false,
    contentType: false,
    processData: false,
  });
  return false;
}

// CLOSE MODAL

const allModalClosers = document.querySelectorAll(".modalCloser");
const allModals = document.querySelectorAll(".modalPopup");


const closeModals = function () {
  [...allModals]?.forEach((el) => {
    el.classList.add("hideModal");
  });
};

[...allModalClosers]?.forEach((closer) => {
  closer?.addEventListener("click", function () {
    closeModals();
  });
});

// Autotab

// Enhanced OTP handling with backspace support and auto-submit
$(".oinputs").keyup(function (e) {
  // Handle backspace - move to previous input and clear current
  if (e.keyCode === 8 && this.value === '') { // Backspace key
    const prevInput = $(this).prev(".oinputs");
    if (prevInput.length) {
      prevInput.focus();
      prevInput.val('');
    }
  }
  // Handle normal input - move to next input
  else if (this.value.length == this.maxLength) {
    $(this).next(".oinputs").focus();
    
    // Check if all OTP inputs in the current form are filled
    const form = $(this).closest('form');
    if (form.length) {
      const allOtpInputs = form.find('input[name="otp"]');
      const allFilled = allOtpInputs.toArray().every(inp => $(inp).val().length === 1);
      
      if (allFilled && allOtpInputs.length === 6) {
        // All 6 digits entered - auto-submit the form
        setTimeout(function() {
          const formId = form.attr('id');
          if (formId === 'singupotp' && typeof loginsingupotp === 'function') {
            loginsingupotp();
          } else if (formId === 'forgototppwd' && typeof forgotpasswordotp === 'function') {
            forgotpasswordotp();
          }
        }, 100);
      }
    }
  }
});
// ///////////

// OTP pasting and Typing code

const otpSource = document.querySelector(".otpSource");
const otpIp = document.querySelectorAll(".otpIp");

function otpHandler() {
  const otpData = otpSource.value;
  console.log(otpData.length);
  if (otpData.length == 6 && "onpaste" in otpSource) {
    for (i = 0; i < otpData.length; i++) {
      otpIp[i].value = otpData[i];
    }
    // Auto-submit when OTP is pasted
    setTimeout(function() {
      const form = otpSource.closest('form');
      if (form) {
        const formId = form.id;
        if (formId === 'singupotp' && typeof loginsingupotp === 'function') {
          loginsingupotp();
        } else if (formId === 'forgototppwd' && typeof forgotpasswordotp === 'function') {
          forgotpasswordotp();
        }
      }
    }, 100);
  } else if (otpData.length == 1) {
    otpSource.maxLength = 1;
  }
}

if (otpSource) {
  otpSource.addEventListener("input", otpHandler);
}
