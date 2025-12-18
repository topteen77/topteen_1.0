function loginsingup() {
  let phoneEmail = document.getElementById("mobileEmail").value;
  if (validateLoginSignup(phoneEmail) == false) {
    document.getElementById("errorMsgSinguplogin").innerHTML =
      (window.LOGIN_MODE === 'parent'
        ? "Please enter valid mobile number"
        : "Please enter valid email or mobile number");
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
        // Institute-student accounts should use password login (not OTP)
        if (data.is_institute_student) {
          loginremoveunusetag();
          var xPwd = document.createElement("input");
          xPwd.setAttribute("type", "hidden");
          xPwd.setAttribute("value", data.enc_user_name);
          xPwd.setAttribute("id", "encloginusername");
          xPwd.setAttribute("name", "enc_user_name");
          document.getElementById("loginpwd").appendChild(xPwd);
          document.getElementById("loginpwdname").textContent = data.user_name;
          document.getElementById("loginpwdDiv").classList.remove("hideModal");
          setTimeout(function() {
            const passwordInput = document.querySelector('#loginpwd input[name="password"]');
            if (passwordInput) passwordInput.focus();
          }, 100);
          return;
        }

        // For template20 OTP-first pages, jump straight to OTP login flow
        if (typeof showLoginWithOtp === 'function' && document.getElementById('loginOtpEmail')) {
          try {
            showLoginWithOtp();
            document.getElementById('loginOtpEmail').value = data.user_name;
            if (typeof sendLoginOtp === 'function') {
              sendLoginOtp();
              return;
            }
          } catch (e) {
            // fallback to old modal flow below
          }
        }

        // Fallback: old password modal flow
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
          fireAlert("Network error. Please check your internet connection and try again", "error");
        } else {
          // Try to get specific error message from response
          var errorMsg = "Unable to process your request. Please try again";
          try {
            if (xhr.responseJSON && xhr.responseJSON.message) {
              errorMsg = xhr.responseJSON.message;
            } else if (xhr.responseText) {
              var errorData = JSON.parse(xhr.responseText);
              if (errorData.message) {
                errorMsg = errorData.message;
              }
            }
          } catch (e) {
            // Use default message if parsing fails
          }
          fireAlert(errorMsg, "error");
        }
      } catch (e) {
        fireAlert("Unable to process your request. Please refresh the page and try again", "error");
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
  phoneEmail = (phoneEmail || '').trim();
  if (window.LOGIN_MODE === 'parent') {
    return validatePhone(phoneEmail);
  }
  return validateEmail(phoneEmail) || validatePhone(phoneEmail);
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

function validatePhone(value) {
  // Strict Indian 10-digit mobile
  return /^[6-9]\d{9}$/.test(value);
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

function handleOtpSubmit() {
  // Check if this is a login OTP flow (has loginotpusername field) or signup flow
  var form = document.getElementById("singupotp");
  var loginOtpUsername = document.getElementById("loginotpusername");
  
  if (loginOtpUsername) {
    // This is a login OTP flow
    return loginwithotp();
  } else {
    // This is a signup OTP flow
    return loginsingupotp();
  }
}

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
              otperrtag.textContent = "Unable to proceed. Please start the signup process again.";
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
          fireAlert("Network error. Please check your internet connection and try again", "error");
        } else {
          // Try to get specific error message from response
          var errorMsg = "Unable to process your request. Please try again";
          try {
            if (xhr.responseJSON && xhr.responseJSON.message) {
              errorMsg = xhr.responseJSON.message;
            } else if (xhr.responseText) {
              var errorData = JSON.parse(xhr.responseText);
              if (errorData.message) {
                errorMsg = errorData.message;
              }
            }
          } catch (e) {
            // Use default message if parsing fails
          }
          fireAlert(errorMsg, "error");
        }
      } catch (e) {
        fireAlert("Unable to process your request. Please refresh the page and try again", "error");
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

// Prevent double submission
var isSubmittingSignup = false;

function loginsinguppwd() {
  // Prevent double submission
  if (isSubmittingSignup) {
    console.log("Signup already in progress, ignoring duplicate submission");
    return false;
  }
  
  var formData = new FormData(document.getElementById("singuppwd"));
  
  // Debug: Log password values (remove in production)
  var password = formData.get("password");
  var confirmPassword = formData.get("confirm_password");
  console.log("Password length:", password ? password.length : 0);
  console.log("Confirm password length:", confirmPassword ? confirmPassword.length : 0);
  console.log("Passwords match:", password === confirmPassword);
  
  if (validatepwd(formData) == false) {
    return false;
  }
  
  // Clear any previous error messages
  var otperrtag = document.getElementById("errorMsgOtpSinguploginpwd");
  if (otperrtag) {
    otperrtag.textContent = "";
  }
  
  // Disable submit button and set submitting flag
  isSubmittingSignup = true;
  var submitButton = document.querySelector('#singuppwd button[type="submit"]');
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = "Creating Account...";
    submitButton.style.opacity = "0.6";
    submitButton.style.cursor = "not-allowed";
  }
  
  // Helper function to get cookie value
  function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
  
  console.log("🚀 Starting AJAX request to:", usersloginsignuppwd);
  
  $.ajax({
    type: "POST",
    url: usersloginsignuppwd,
    data: formData,
    dataType: 'json',  // Explicitly expect JSON response
    beforeSend: function(xhr) {
      console.log("📤 AJAX beforeSend called");
      // Ensure CSRF token is included - get from form or cookies
      var csrfToken = $('[name=csrfmiddlewaretoken]').val();
      if (!csrfToken) {
        // Get CSRF token from cookies
        csrfToken = getCookie('csrftoken');
      }
      if (csrfToken) {
        xhr.setRequestHeader("X-CSRFToken", csrfToken);
        console.log("✅ CSRF token set");
      } else {
        console.log("⚠️ No CSRF token found");
      }
    },
    success: function (data) {
      console.log("=== SIGNUP PASSWORD RESPONSE ===");
      console.log("✅ SUCCESS CALLBACK CALLED!");
      console.log("Full response:", JSON.stringify(data, null, 2));
      console.log("Response type:", typeof data);
      console.log("Has success:", data && data.success);
      console.log("Redirect URL:", data && data.redirect_url);
      console.log("Message:", data && data.message);
      
      isSubmittingSignup = false;
      
      // Re-enable submit button
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = "Create account";
        submitButton.style.opacity = "1";
        submitButton.style.cursor = "pointer";
      }
      
      // Check if data is a string (needs parsing) or object
      if (typeof data === 'string') {
        try {
          console.log("Parsing string response...");
          data = JSON.parse(data);
          console.log("Parsed data:", data);
        } catch (e) {
          console.error("Failed to parse response:", e);
          var otperrtag = document.getElementById("errorMsgOtpSinguploginpwd");
          if (otperrtag) {
            otperrtag.textContent = "Error processing response. Please try again.";
          }
          return;
        }
      }
      
      // Check for success flag
      if (data && (data.success === true || data.success === 'true')) {
        console.log("✅ Success flag found, proceeding with redirect...");
        
        // Close password modal
        var signUpPwdDiv = document.getElementById("signUpPwdDiv");
        if (signUpPwdDiv) {
          signUpPwdDiv.classList.add("hideModal");
          console.log("✅ Modal closed");
        }
        
        // Redirect immediately
        var redirectUrl = data.redirect_url || '/user/dashboard';
        console.log("Redirect URL:", redirectUrl);
        console.log("Redirect URL type:", typeof redirectUrl);
        console.log("Redirect URL valid:", redirectUrl && redirectUrl !== 'undefined' && redirectUrl !== 'null' && redirectUrl !== '');
        
        // Force immediate redirect
        if (redirectUrl && redirectUrl !== 'undefined' && redirectUrl !== 'null' && redirectUrl !== '') {
          console.log("🚀 Redirecting to:", redirectUrl);
          // Use replace for immediate redirect
          window.location.replace(redirectUrl);
        } else {
          // Fallback redirect
          console.log("⚠️ Using fallback URL: /user/dashboard");
          window.location.replace('/user/dashboard');
        }
      } else {
        console.log("❌ No success flag found in response");
        console.log("Response data:", data);
        // Show error message from server
        var otperrtag = document.getElementById("errorMsgOtpSinguploginpwd");
        if (otperrtag && data.message) {
          otperrtag.textContent = data.message;
        } else if (otperrtag) {
          otperrtag.textContent = "Unable to create account. Please check your information and try again.";
        }
      }
    },
    error: function (xhr, status, error) {
      console.log("=== AJAX ERROR CALLBACK ===");
      console.log("Status:", status);
      console.log("Error:", error);
      console.log("Status code:", xhr.status);
      console.log("Response text:", xhr.responseText);
      console.log("Response JSON:", xhr.responseJSON);
      
      isSubmittingSignup = false;
      
      // Re-enable submit button
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = "Create account";
        submitButton.style.opacity = "1";
        submitButton.style.cursor = "pointer";
      }
      
      try {
        // Try to parse error response
        var errorMessage = "Unable to create your account. Please check your information and try again.";
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
          // CSRF token expired or invalid - refresh page to get new token
          fireAlert("Session expired. Refreshing page...", "warning");
          setTimeout(function() {
            window.location.reload();
          }, 1500);
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
  
  // Validate confirm password field exists
  var confirmPassword = formData.get("confirm_password");
  if (!confirmPassword || confirmPassword === "") {
    var otperrtag = document.getElementById("errorMsgOtpSinguploginpwd");
    otperrtag.textContent = "Please confirm your password. Try Again";
    return false;
  }
  
  // Validate password match (trim whitespace for comparison)
  var password = formData.get("password");
  var confirmPwd = confirmPassword;
  
  // Handle null/undefined cases
  if (!password) password = "";
  if (!confirmPwd) confirmPwd = "";
  
  // Trim and compare
  password = password.trim();
  confirmPwd = confirmPwd.trim();
  
  if (password !== confirmPwd) {
    var otperrtag = document.getElementById("errorMsgOtpSinguploginpwd");
    otperrtag.textContent = "Passwords do not match. Please make sure both passwords are the same.";
    // Also update the visual match indicator
    var matchMsg = document.getElementById("passwordMatchMsg");
    if (matchMsg) {
      matchMsg.textContent = "✗ Passwords do not match";
      matchMsg.style.color = "#ef4444";
      matchMsg.style.display = "block";
    }
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
          fireAlert("Network error. Please check your internet connection and try again", "error");
        } else {
          // Try to get specific error message from response
          var errorMsg = "Unable to process your request. Please try again";
          try {
            if (xhr.responseJSON && xhr.responseJSON.message) {
              errorMsg = xhr.responseJSON.message;
            } else if (xhr.responseText) {
              var errorData = JSON.parse(xhr.responseText);
              if (errorData.message) {
                errorMsg = errorData.message;
              }
            }
          } catch (e) {
            // Use default message if parsing fails
          }
          fireAlert(errorMsg, "error");
        }
      } catch (e) {
        fireAlert("Unable to process your request. Please refresh the page and try again", "error");
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

function loginwithotpshow() {
  // Close password modal
  document.getElementById("loginpwdDiv").classList.add("hideModal");
  
  // Get the username from login password modal
  var loginPwdName = document.getElementById("loginpwdname");
  var username = loginPwdName ? loginPwdName.textContent.trim() : "";
  
  if (!username) {
    fireAlert("Unable to retrieve user information. Please close and reopen the login window", "error");
    return false;
  }
  
  // Send OTP directly using resend OTP endpoint (works for both new and existing users)
  var formData = new FormData();
  formData.append("user_name", username);
  
  $.ajax({
    type: "POST",
    url: usersresendotp,
    data: formData,
    success: function (data) {
      // Remove any existing username input from OTP form
      var existingInput = document.getElementById("loginotpusername");
      if (existingInput) {
        existingInput.remove();
      }
      
      // Remove signup username input if exists
      var signupUsernameInput = document.getElementById("signupusername");
      if (signupUsernameInput) {
        signupUsernameInput.remove();
      }
      
      // Add username to OTP form for login flow
      var x = document.createElement("input");
      x.setAttribute("type", "hidden");
      x.setAttribute("value", username);
      x.setAttribute("id", "loginotpusername");
      x.setAttribute("name", "user_name");
      
      var otpForm = document.getElementById("singupotp");
      if (otpForm) {
        otpForm.appendChild(x);
        document.getElementById("signupotpname").textContent = username;
        document.getElementById("otpDiv").classList.remove("hideModal");
        
        // Clear any previous error messages
        var errorMsg = document.getElementById("errorMsgOtpSinguplogin");
        if (errorMsg) {
          errorMsg.textContent = "";
        }
        
        // Reset OTP inputs
        var otpInputs = otpForm.querySelectorAll('input[name="otp"]');
        otpInputs.forEach(function(input) {
          input.value = "";
        });
        
        // Auto-focus on first OTP input
        setTimeout(function() {
          const firstOtpInput = document.querySelector('.otpSource');
          if (firstOtpInput) {
            firstOtpInput.focus();
          }
        }, 100);
      }
    },
    error: function (xhr, status, error) {
      fireAlert("Unable to send OTP. Please check your email/mobile and try again", "error");
    },
    cache: false,
    contentType: false,
    processData: false,
  });
  return false;
}

function loginwithotp() {
  var formData = new FormData(document.getElementById("singupotp"));
  if (validateotp(formData) == false) {
    return false;
  }
  $.ajax({
    type: "POST",
    url: usersloginotp,
    data: formData,
    success: function (data) {
      if (data.otp_verify != true || data.success != true) {
        var otperrtag = document.getElementById("errorMsgOtpSinguplogin");
        if (otperrtag) {
          otperrtag.textContent = data.message || "The otp you entered is incorrect. Try Again";
        }
      }

      if (data.otp_verify == true && data.success == true) {
        // OTP verified and user logged in - redirect to dashboard
        loginsingupotpremoveunusetag();
        if (data.redirect_url) {
          window.location.href = data.redirect_url;
        } else {
          window.location.href = '/user/dashboard';
        }
      }
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
          fireAlert("Network error. Please check your internet connection and try again", "error");
        } else {
          // Try to get specific error message from response
          var errorMsg = "Unable to process your request. Please try again";
          try {
            if (xhr.responseJSON && xhr.responseJSON.message) {
              errorMsg = xhr.responseJSON.message;
            } else if (xhr.responseText) {
              var errorData = JSON.parse(xhr.responseText);
              if (errorData.message) {
                errorMsg = errorData.message;
              }
            }
          } catch (e) {
            // Use default message if parsing fails
          }
          fireAlert(errorMsg, "error");
        }
      } catch (e) {
        fireAlert("Unable to process your request. Please refresh the page and try again", "error");
      }
    },
    cache: false,
    contentType: false,
    processData: false,
  });
  return false;
}

function forgotpasswordshow() {
  // Get the email from login password modal
  var loginPwdName = document.getElementById("loginpwdname");
  var email = loginPwdName ? loginPwdName.textContent.trim() : "";
  
  if (!email) {
    fireAlert("Unable to retrieve email. Please close and reopen the login window", "error");
    return false;
  }
  
  // Close login password modal
  document.getElementById("loginpwdDiv").classList.add("hideModal");
  
  // Send OTP directly to the registered email
  var formData = new FormData();
  formData.append("user_name", email);
  
  $.ajax({
    type: "POST",
    url: usersforgotpassword,
    data: formData,
    success: function (data) {
      if (data.success) {
        // Remove any existing username input from forgot password OTP form
        var existingInput = document.getElementById("forgotpwdusername");
        if (existingInput) {
          existingInput.remove();
        }
        
        // Add encrypted username to forgot password OTP form
        var x = document.createElement("input");
        x.setAttribute("type", "hidden");
        x.setAttribute("value", data.enc_user_name);
        x.setAttribute("id", "forgotpwdusername");
        x.setAttribute("name", "user_name");
        
        var forgotOtpForm = document.getElementById("forgototppwd");
        if (forgotOtpForm) {
          forgotOtpForm.appendChild(x);
          document.getElementById("forgototppwdname").textContent = data.user_name || email;
          document.getElementById("forgotpwdotpDiv").classList.remove("hideModal");
          
          // Clear any previous error messages
          var errorMsg = document.getElementById("errorMsgfotgototp");
          if (errorMsg) {
            errorMsg.textContent = "";
          }
          
          // Reset OTP inputs
          var otpInputs = forgotOtpForm.querySelectorAll('input[name="otp"]');
          otpInputs.forEach(function(input) {
            input.value = "";
          });
          
          // Reset password fields
          var passwordInput = forgotOtpForm.querySelector('input[name="password"]');
          var confirmPasswordInput = forgotOtpForm.querySelector('input[name="confirm_password"]');
          if (passwordInput) passwordInput.value = "";
          if (confirmPasswordInput) confirmPasswordInput.value = "";
          
          // Auto-focus on first OTP input
          setTimeout(function() {
            const firstOtpInput = forgotOtpForm.querySelector('.otpSource');
            if (firstOtpInput) {
              firstOtpInput.focus();
            }
          }, 100);
        }
      } else {
        fireAlert(data.message || "Unable to send OTP. Please try again", "error");
      }
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
          fireAlert("Network error. Please check your internet connection and try again", "error");
        } else {
          var errorMsg = "Unable to send OTP. Please try again";
          try {
            if (xhr.responseJSON && xhr.responseJSON.message) {
              errorMsg = xhr.responseJSON.message;
            } else if (xhr.responseText) {
              var errorData = JSON.parse(xhr.responseText);
              if (errorData.message) {
                errorMsg = errorData.message;
              }
            }
          } catch (e) {
            // Use default message if parsing fails
          }
          fireAlert(errorMsg, "error");
        }
      } catch (e) {
        fireAlert("Unable to process your request. Please refresh the page and try again", "error");
      }
    },
    cache: false,
    contentType: false,
    processData: false,
  });
  return false;
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
          fireAlert("Network error. Please check your internet connection and try again", "error");
        } else {
          // Try to get specific error message from response
          var errorMsg = "Unable to process your request. Please try again";
          try {
            if (xhr.responseJSON && xhr.responseJSON.message) {
              errorMsg = xhr.responseJSON.message;
            } else if (xhr.responseText) {
              var errorData = JSON.parse(xhr.responseText);
              if (errorData.message) {
                errorMsg = errorData.message;
              }
            }
          } catch (e) {
            // Use default message if parsing fails
          }
          fireAlert(errorMsg, "error");
        }
      } catch (e) {
        fireAlert("Unable to process your request. Please refresh the page and try again", "error");
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
          fireAlert("Network error. Please check your internet connection and try again", "error");
        } else {
          // Try to get specific error message from response
          var errorMsg = "Unable to process your request. Please try again";
          try {
            if (xhr.responseJSON && xhr.responseJSON.message) {
              errorMsg = xhr.responseJSON.message;
            } else if (xhr.responseText) {
              var errorData = JSON.parse(xhr.responseText);
              if (errorData.message) {
                errorMsg = errorData.message;
              }
            }
          } catch (e) {
            // Use default message if parsing fails
          }
          fireAlert(errorMsg, "error");
        }
      } catch (e) {
        fireAlert("Unable to process your request. Please refresh the page and try again", "error");
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
    fireAlert("Unable to resend OTP. Please check your email/mobile and try again.", "error");
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
          fireAlert("Network error. Please check your internet connection and try again", "error");
        } else {
          // Try to get specific error message from response
          var errorMsg = "Unable to process your request. Please try again";
          try {
            if (xhr.responseJSON && xhr.responseJSON.message) {
              errorMsg = xhr.responseJSON.message;
            } else if (xhr.responseText) {
              var errorData = JSON.parse(xhr.responseText);
              if (errorData.message) {
                errorMsg = errorData.message;
              }
            }
          } catch (e) {
            // Use default message if parsing fails
          }
          fireAlert(errorMsg, "error");
        }
      } catch (e) {
        fireAlert("Unable to process your request. Please refresh the page and try again", "error");
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
          fireAlert("Network error. Please check your internet connection and try again", "error");
        } else {
          // Try to get specific error message from response
          var errorMsg = "Unable to process your request. Please try again";
          try {
            if (xhr.responseJSON && xhr.responseJSON.message) {
              errorMsg = xhr.responseJSON.message;
            } else if (xhr.responseText) {
              var errorData = JSON.parse(xhr.responseText);
              if (errorData.message) {
                errorMsg = errorData.message;
              }
            }
          } catch (e) {
            // Use default message if parsing fails
          }
          fireAlert(errorMsg, "error");
        }
      } catch (e) {
        fireAlert("Unable to process your request. Please refresh the page and try again", "error");
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
