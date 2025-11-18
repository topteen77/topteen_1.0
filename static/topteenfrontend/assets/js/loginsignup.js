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
        loginsingupotpremoveunusetag();
        var x = document.createElement("input");
        x.setAttribute("type", "hidden");
        x.setAttribute("value", data.enc_user_name);
        x.setAttribute("id", "encsignupusername");
        x.setAttribute("name", "enc_user_name");
        document.getElementById("singuppwd").appendChild(x);
        document.getElementById("signuppwdname").textContent = data.user_name;
        document.getElementById("signUpPwdDiv").classList.remove("hideModal");
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
  $.ajax({
    type: "POST",
    url: usersloginsignuppwd,
    data: formData,
    success: async function (data) {
      if (data.success) {
        // alert("Account created succefully");
        await fireAlert("Account created successfully", "success");
        setTimeout(() => {
          window.location.reload();
        }, 10);
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

function validatepwd(formData) {
  if (formData.get("password") == "") {
    var otperrtag = document.getElementById("errorMsgOtpSinguploginpwd");
    otperrtag.textContent = "All fields required. Try Again";
    return false;
  }
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

// Enhanced OTP handling with backspace support
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
  } else if (otpData.length == 1) {
    otpSource.maxLength = 1;
  }
}

if (otpSource) {
  otpSource.addEventListener("input", otpHandler);
}
