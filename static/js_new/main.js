

// Chat bot


//const API_URL = `https://43.204.127.118:8001/`;
// const API_URL = `http://demo.topteen.in/bot/`;

// Chat bot
let API_URL;
if (window.location.hostname === "http://localhost/topteen/") {
  API_URL = "http://demo.topteen.in/bot/";
} else {
  API_URL = "https://demo.topteen.in/bot/";
}

const chatBody = document.querySelector(".chat-body");
const messageInput = document.querySelector(".message-input");
const sendMessage = document.querySelector("#send-message");
const fileInput = document.querySelector("#file-input");
const fileUploadWrapper = document.querySelector(".file-upload-wrapper");
const fileCancelButton = fileUploadWrapper.querySelector("#file-cancel");
const chatbotToggler = document.querySelector("#chatbot-toggler");
const closeChatbot = document.querySelector("#close-chatbot");

// Generate a random UUID
function uuidv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'
    .replace(/[xy]/g, function (c) {
      const r = Math.random() * 16 | 0,
        v = c == 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
}

const unique_session_id = uuidv4();

// Function to check if the browser is closing
window.addEventListener('beforeunload', (event) => {
  fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      uuid: unique_session_id,
      is_left: true
    }),
  });
});

// Function to track user inactivity
let lastActivityTime = Date.now();
const inactivityTimeout = 600000; // 10 minutes in milliseconds

function trackInactivity() {
  const currentTime = Date.now();
  const timeElapsed = currentTime - lastActivityTime;

  if (timeElapsed > inactivityTimeout) {
    fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        uuid: unique_session_id,
        is_left: true
      }),
    });
  }
  lastActivityTime = currentTime;
}

document.addEventListener('mousemove', trackInactivity);
document.addEventListener('keydown', trackInactivity);
document.addEventListener('scroll', trackInactivity);
document.addEventListener('click', trackInactivity);
setInterval(trackInactivity, 10000);

// API setup
const userData = {
  message: null,
  file: {
    data: null,
    mime_type: null,
  },
};

const chatHistory = [];
const initialInputHeight = messageInput.scrollHeight;

const createMessageElement = (content, ...classes) => {
  const div = document.createElement("div");
  div.classList.add("message", ...classes);
  div.innerHTML = content;
  return div;
};

const generateBotResponse = async (incomingMessageDiv) => {
  const messageElement = incomingMessageDiv.querySelector(".message-text");
  chatHistory.push({
    role: "user",
    parts: [{ text: userData.message }, ...(userData.file.data ? [{ inline_data: userData.file }] : [])],
  });

  const requestOptions = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user: userData.message,
      uuid: unique_session_id
    }),
  };

  try {
    const response = await fetch(API_URL, requestOptions);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error.message);
    const apiResponseText = data['AI'];
    messageElement.innerHTML = apiResponseText;
    chatHistory.push({
      role: "model",
      parts: [{ text: apiResponseText }],
    });
  } catch (error) {
    console.log(error);
    messageElement.innerText = error.message;
    messageElement.style.color = "#ff0000";
  } finally {
    userData.file = {};
    incomingMessageDiv.classList.remove("thinking");
    chatBody.scrollTo({ top: chatBody.scrollHeight, behavior: "smooth" });
  }
};

const handleOutgoingMessage = (e) => {
  e.preventDefault();
  userData.message = messageInput.value.trim();
  messageInput.value = "";
  messageInput.dispatchEvent(new Event("input"));
  fileUploadWrapper.classList.remove("file-uploaded");

  const messageContent = `
        <div class="message-text"></div>
        ${userData.file.data ? `<img src="data:${userData.file.mime_type};base64,${userData.file.data}" class="attachment" />` : ""}
    `;
  const outgoingMessageDiv = createMessageElement(messageContent, "user-message");
  outgoingMessageDiv.querySelector(".message-text").innerText = userData.message;
  chatBody.appendChild(outgoingMessageDiv);
  chatBody.scrollTo({ top: chatBody.scrollHeight, behavior: "smooth" });

  setTimeout(() => {
    const messageContent = `
            <svg class="bot-avatar" xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 1024 1024">
                <path d="M738.3 287.6H285.7c-59 0-106.8 47.8-106.8 106.8v303.1c0 59 47.8 106.8 106.8 106.8h81.5v111.1c0 .7.8 1.1 1.4.7l166.9-110.6 41.8-.8h117.4l43.6-.4c59 0 106.8-47.8 106.8-106.8V394.5c0-59-47.8-106.9-106.8-106.9zM351.7 448.2c0-29.5 23.9-53.5 53.5-53.5s53.5 23.9 53.5 53.5-23.9 53.5-53.5 53.5-53.5-23.9-53.5-53.5zm157.9 267.1c-67.8 0-123.8-47.5-132.3-109h264.6c-8.6 61.5-64.5 109-132.3 109zm110-213.7c-29.5 0-53.5-23.9-53.5-53.5s23.9-53.5 53.5-53.5 53.5 23.9 53.5 53.5-23.9 53.5-53.5 53.5zM867.2 644.5V453.1h26.5c19.4 0 35.1 15.7 35.1 35.1v121.1c0 19.4-15.7 35.1-35.1 35.1h-26.5zM95.2 609.4V488.2c0-19.4 15.7-35.1 35.1-35.1h26.5v191.3h-26.5c-19.4 0-35.1-15.7-35.1-35.1zM561.5 149.6c0 23.4-15.6 43.3-36.9 49.7v44.9h-30v-44.9c-21.4-6.5-36.9-26.3-36.9-49.7 0-28.6 23.3-51.9 51.9-51.9s51.9 23.3 51.9 51.9z"/>
            </svg>
            <div class="message-text">
                <div class="thinking-indicator flex items-center">
                    <div class="fs-14 fw-normal me-2 shine-text py-0" id="word"></div>
                    <div class="dot"></div>
                    <div class="dot"></div>
                    <div class="dot"></div>
                </div>
            </div>
        `;
    const incomingMessageDiv = createMessageElement(messageContent, "bot-message", "thinking");
    chatBody.appendChild(incomingMessageDiv);
    chatBody.scrollTo({ top: chatBody.scrollHeight, behavior: "smooth" });
    initWordAnimation();
    generateBotResponse(incomingMessageDiv);
  }, 600);
};

// Show AI message after 2 seconds - DISABLED: Now handled by chatbot.js auto-open functionality
// setTimeout(() => {
//   document.querySelector('.ai-chat-message').classList.add('show');
// }, 4000);

// Handle Let's Chat button click - with null check
const letsChatBtn = document.querySelector('.lest-chart-sart');
if (letsChatBtn) {
  letsChatBtn.addEventListener('click', (e) => {
    e.preventDefault();
    const aiMessage = document.querySelector('.ai-chat-message');
    if (aiMessage) aiMessage.style.display = 'none';
    document.body.classList.add('show-chatbot');
  });
}

// Add close functionality for the close button - with null check
const closeIcon = document.querySelector('.ai-chat-message .close-icon');
if (closeIcon) {
  closeIcon.addEventListener('click', (e) => {
    e.stopPropagation();
    const aiMessage = document.querySelector('.ai-chat-message');
    if (aiMessage) aiMessage.style.display = 'none';
  });
}

// Hide AI message when chatbot is opened through toggler - with null check
if (chatbotToggler) {
  chatbotToggler.addEventListener('click', () => {
    const aiMessage = document.querySelector('.ai-chat-message');
    if (aiMessage) aiMessage.style.display = 'none';
  });
}

// Initialize word animation
const initWordAnimation = () => {
  let count = -1;
  const wordElement = document.getElementById('word');
  const initText = "Thinking... Give me a sec!";
  const wordsArray = [
    " Processing your request",
    " Working on it! One moment",
    " Typing",
    " Typing"
  ];
  wordElement.textContent = initText;

  setInterval(() => {
    count++;
    wordElement.style.opacity = '0';
    setTimeout(() => {
      wordElement.textContent = wordsArray[count % wordsArray.length];
      wordElement.style.opacity = '1';
    }, 400);
  }, 5500);
};

// Adjust input field height dynamically
messageInput.addEventListener("input", () => {
  messageInput.style.height = `${initialInputHeight}px`;
  messageInput.style.height = `${messageInput.scrollHeight}px`;
  document.querySelector(".chat-form").style.borderRadius = messageInput.scrollHeight > initialInputHeight ? "15px" : "32px";
});

// Handle Enter key press for sending messages
messageInput.addEventListener("keydown", (e) => {
  const userMessage = e.target.value.trim();
  if (e.key === "Enter" && !e.shiftKey && userMessage && window.innerWidth > 768) {
    handleOutgoingMessage(e);
  }
});

// Handle file input change and preview the selected file
fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    fileInput.value = "";
    fileUploadWrapper.querySelector("img").src = e.target.result;
    fileUploadWrapper.classList.add("file-uploaded");
    const base64String = e.target.result.split(",")[1];
    userData.file = {
      data: base64String,
      mime_type: file.type,
    };
  };
  reader.readAsDataURL(file);
});

// Cancel file upload
fileCancelButton.addEventListener("click", () => {
  userData.file = {};
  fileUploadWrapper.classList.remove("file-uploaded");
});

// Initialize emoji picker and handle emoji selection
const picker = new EmojiMart.Picker({
  theme: "light",
  skinTonePosition: "none",
  previewPosition: "none",
  onEmojiSelect: (emoji) => {
    const { selectionStart: start, selectionEnd: end } = messageInput;
    messageInput.setRangeText(emoji.native, start, end, "end");
    messageInput.focus();
  },
  onClickOutside: (e) => {
    if (e.target.id === "emoji-picker") {
      document.body.classList.toggle("show-emoji-picker");
    } else {
      document.body.classList.remove("show-emoji-picker");
    }
  },
});

document.querySelector(".chat-form").appendChild(picker);

sendMessage.addEventListener("click", (e) => handleOutgoingMessage(e));
document.querySelector("#file-upload").addEventListener("click", () => fileInput.click());
closeChatbot.addEventListener("click", () => document.body.classList.remove("show-chatbot"));
chatbotToggler.addEventListener("click", () => document.body.classList.toggle("show-chatbot"));


// Close chatbot when clicking outside of it


// header fixed //
const header = document.querySelector('.header');
window.addEventListener('scroll', () => {
  if (window.scrollY > 50) {
    header.classList.add('shrink');
  } else {
    header.classList.remove('shrink');
  }
});





// Toggle to show and hide navbar menu - Cross-browser compatible
document.addEventListener('DOMContentLoaded', function() {
  const navbarMenu = document.getElementById("menu");
  const burgerMenu = document.getElementById("burger");
  
  // Check if elements exist before adding event listeners
  if (burgerMenu && navbarMenu) {
    // Use both click and touchstart for better mobile support
    burgerMenu.addEventListener("click", function(e) {
      e.preventDefault();
      e.stopPropagation();
      navbarMenu.classList.toggle("is-active");
      burgerMenu.classList.toggle("is-active");
    });
    
    // Touch support for mobile devices
    burgerMenu.addEventListener("touchstart", function(e) {
      e.preventDefault();
      e.stopPropagation();
      navbarMenu.classList.toggle("is-active");
      burgerMenu.classList.toggle("is-active");
    });
    
    // Close menu when clicking outside
    document.addEventListener("click", function(e) {
      if (!burgerMenu.contains(e.target) && !navbarMenu.contains(e.target)) {
        navbarMenu.classList.remove("is-active");
        burgerMenu.classList.remove("is-active");
      }
    });
  }
});

// Toggle to show and hide dropdown menu
const dropdown = document.querySelectorAll(".dropdown");

dropdown.forEach((item) => {
  const dropdownToggle = item.querySelector(".dropdown-toggle");

  dropdownToggle.addEventListener("click", () => {
    const dropdownShow = document.querySelector(".dropdown-show");
    toggleDropdownItem(item);

    // Remove 'dropdown-show' class from other dropdown
    if (dropdownShow && dropdownShow != item) {
      toggleDropdownItem(dropdownShow);
    }
  });
});

// Function to display the dropdown menu
const toggleDropdownItem = (item) => {
  const dropdownContent = item.querySelector(".dropdown-content");

  // Remove other dropdown that have 'dropdown-show' class
  if (item.classList.contains("dropdown-show")) {
    dropdownContent.removeAttribute("style");
    item.classList.remove("dropdown-show");
  } else {
    // Added max-height on active 'dropdown-show' class
    dropdownContent.style.height = dropdownContent.scrollHeight + "px";
    item.classList.add("dropdown-show");
  }
};

// Fixed dropdown menu on window resizing
window.addEventListener("resize", () => {
  if (window.innerWidth > 992) {
    document.querySelectorAll(".dropdown-content").forEach((item) => {
      item.removeAttribute("style");
    });
    dropdown.forEach((item) => {
      item.classList.remove("dropdown-show");
    });
  }
});

// Fixed navbar menu on window resizing
window.addEventListener("resize", () => {
  if (window.innerWidth > 992) {
    if (navbarMenu.classList.contains("is-active")) {
      navbarMenu.classList.remove("is-active");
      burgerMenu.classList.remove("is-active");
    }
  }
});

// scrolling js //

const scrollers = document.querySelectorAll(".scroller");

if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  addAnimation();
}

function addAnimation() {
  scrollers.forEach(scroller => {
    scroller.setAttribute("data-animated", true);

    const scrollerInner = scroller.querySelector('.scroller__inner');
    if (!scrollerInner) return;
    const scrollerContent = Array.from(scrollerInner.children);

    scrollerContent.forEach(item => {
      const duplicatedItem = item.cloneNode(true);
      duplicatedItem.setAttribute('aria-hidden', true);
      scrollerInner.appendChild(duplicatedItem);
    });
  });
}

// scrolling js //


// Auto Generate video Thumbnails //


document.addEventListener("DOMContentLoaded", function () {
  var videoModal = document.getElementById("videoModal");
  var videoFrame = document.getElementById("videoFrame");
  var videoLinks = document.querySelectorAll(".video-link");

  // Only initialize video modal if elements exist (not on login page)
  if (videoModal && videoFrame) {
    videoLinks.forEach(function (link) {
      link.addEventListener("click", function () {
        var videoSrc = this.getAttribute("data-video");
        if (videoFrame) {
          videoFrame.src = videoSrc;
        }
      });
    });

    videoModal.addEventListener("hidden.bs.modal", function () {
      if (videoFrame) {
        videoFrame.src = ""; // Stop video when modal is closed
      }
    });
  }
});

function captureThumbnail(video, canvas) {
  const ctx = canvas.getContext("2d");

  // Explicitly load the video
  video.preload = "metadata";
  video.load(); // Force loading

  // Log video state for debugging
  console.log(`Processing video: ${video.currentSrc}`);

  video.addEventListener("loadedmetadata", () => {
    console.log(`Metadata loaded for ${video.currentSrc}: ${video.videoWidth}x${video.videoHeight}`);
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    // Seek to a safe point (2s or 10% of duration)
    const seekTime = Math.min(2, video.duration * 0.1) || 2;
    video.currentTime = seekTime;
  }, { once: true });

  video.addEventListener("seeked", () => {
    console.log(`Seeked to ${video.currentTime} for ${video.currentSrc}`);
    try {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      console.log(`Thumbnail drawn for ${video.currentSrc}`);
    } catch (e) {
      console.error(`Error drawing thumbnail for ${video.currentSrc}:`, e);
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "#fff";
      ctx.font = "20px Arial";
      ctx.fillText("Thumbnail Unavailable", canvas.width / 4, canvas.height / 2);
    }
  }, { once: true });

  video.addEventListener("error", (e) => {
    console.error(`Error loading video ${video.currentSrc}:`, e);
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#fff";
    ctx.font = "20px Arial";
    ctx.fillText("Video Unavailable", canvas.width / 4, canvas.height / 2);
  }, { once: true });
}

function generateThumbnails() {
  const videos = document.querySelectorAll(".videoPlayer");
  const canvases = document.querySelectorAll(".thumbnailCanvas");

  if (videos.length !== canvases.length) {
    console.error("Mismatch between videos and canvases");
    return;
  }

  videos.forEach((video, index) => {
    const canvas = canvases[index];
    captureThumbnail(video, canvas);
  });
}

// Run on page load
window.addEventListener("load", () => {
  console.log("Page loaded, generating thumbnails...");
  generateThumbnails();
});

// OWL CAROUSEL //


// PSYCHOMETRIC TEST CAROUSEL //
$(document).ready(function ($) {
  $(".psy-carousel").owlCarousel({
    loop: true,
    margin: 20,
    dots: false,
    nav: false,
    autoplay: false,

    responsive: {
      0: {
        items: 1.5,
      },
      768: {
        items: 4
      }
    }

  });

  // PSYCHOMETRIC TEST CAROUSEL //



  // CAREER PLANNING CAROUSEL //

  $(".career-carousel").owlCarousel({
    loop: true,
    margin: 20,
    dots: false,
    nav: false,
    autoplay: false,

    responsive: {
      0: {
        items: 1.2,
      },
      768: {
        items: 3
      }
    }
  });

  $(".who-student").owlCarousel({
    loop: true,
    margin: 20,
    dots: false,
    nav: false,
    autoplay: true,

    responsive: {
      0: {
        items: 1.2,
      },
      768: {
        items: 4
      }
    }
  });

  $(".professions").owlCarousel({
    loop: true,
    margin: 20,
    dots: false,
    nav: false,
    autoplay: true,

    responsive: {
      0: {
        items: 1.2,
      },
      768: {
        items: 4
      }
    }
  });

  $(".who-parent").owlCarousel({
    loop: false,
    margin: 20,
    dots: false,
    nav: false,
    autoplay: true,

    responsive: {
      0: {
        items: 1.2,
      },
      768: {
        items: 4
      }
    }
  });



  // CAREER PLANNING CAROUSEL //

  var owl = $(".owl-carousel");
  owl.owlCarousel();
  $(".next-btn").click(function () {
    owl.trigger("next.owl.carousel");
  });
  $(".prev-btn").click(function () {
    owl.trigger("prev.owl.carousel");
  });
  $(".prev-btn").addClass("disabled");
  $(owl).on("translated.owl.carousel", function (event) {
    if ($(".owl-prev").hasClass("disabled")) {
      $(".prev-btn").addClass("disabled");
    } else {
      $(".prev-btn").removeClass("disabled");
    }
    if ($(".owl-next").hasClass("disabled")) {
      $(".next-btn").addClass("disabled");
    } else {
      $(".next-btn").removeClass("disabled");
    }
  });
});

// OWL CAROUSEL //



// Testimonial Script //
'use strict'
// Initialize testimonial script only when DOM is ready
function initTestimonialScript() {
  var testim = document.getElementById("testim");
  if (!testim) {
    console.log('[Testimonial] Testim element not found');
    return; // Exit early if testim element doesn't exist
  }
  
  var testimDotsEl = document.getElementById("testim-dots"),
    testimContentEl = document.getElementById("testim-content"),
    testimDemoEl = document.getElementById("testim-background"),
    testimDots = (testimDotsEl && testimDotsEl.children) ? Array.prototype.slice.call(testimDotsEl.children) : [],
    testimContent = (testimContentEl && testimContentEl.children) ? Array.prototype.slice.call(testimContentEl.children) : [],
    testimDemo = (testimDemoEl && testimDemoEl.children) ? Array.prototype.slice.call(testimDemoEl.children) : [],
    testimLeftArrow = document.querySelector(".left-arrow"),
    testimRightArrow = document.querySelector(".right-arrow"),
    testimSpeed = 7500,
    currentSlide = 0,
    currentActive = 0,
    testimTimer,
    testimTimerD,
    touchStartPos,
    touchEndPos,
    touchPosDiff,
    ignoreTouch = 30;

  console.log('[Testimonial] Initializing:', {
    testim: !!testim,
    dots: testimDots.length,
    content: testimContent.length,
    leftArrow: !!testimLeftArrow,
    rightArrow: !!testimRightArrow
  });

  // Testim Script - only run if testimonial elements exist
  if (testim && testimDots.length > 0 && testimContent.length > 0) {
    console.log('[Testimonial] Setting up carousel with', testimContent.length, 'slides');
    // Hide arrows if only one testimonial
    if (testimContent.length <= 1) {
      console.log('[Testimonial] Only one slide, hiding arrows');
      if (testimLeftArrow) testimLeftArrow.style.display = 'none';
      if (testimRightArrow) testimRightArrow.style.display = 'none';
      return; // Exit early if only one testimonial
    }

    function playSlide(slide) {
      if (testimDemo.length >= 2) {
        testimDemo[0].classList.add("active");
        testimDemo[1].classList.add("active");
      }

      for (var k = 0; k < testimDots.length; k++) {
        testimContent[k].classList.remove("active");
        testimContent[k].classList.add("inactive");
        testimDots[k].classList.remove("active");
      }


      if (slide < 0) {
        slide = currentSlide = testimContent.length - 1;
      }

      if (slide > testimContent.length - 1) {
        slide = currentSlide = 0;
      }

      if (testimContent[slide]) {
        testimContent[slide].classList.remove("inactive");
        testimContent[slide].classList.add("active");
        if (testimDots[slide]) {
          testimDots[slide].classList.add("active");
        }
      }

      currentActive = currentSlide;

      clearTimeout(testimTimerD);
      if (testimDemo.length >= 2) {
        testimTimerD = setTimeout(function () {
          testimDemo[0].classList.remove("active");
          testimDemo[1].classList.remove("active");
        }, testimSpeed / 2);
      }

      clearTimeout(testimTimer);
      testimTimer = setTimeout(function () {
        playSlide(currentSlide += 1);
      }, testimSpeed);
    }

    // Initialize first slide
    playSlide(0);

    if (testimLeftArrow) {
      testimLeftArrow.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        console.log('[Testimonial] Left arrow clicked, current slide:', currentSlide);
        clearTimeout(testimTimer);
        playSlide(currentSlide -= 1);
      });
      console.log('[Testimonial] Left arrow listener attached');
    } else {
      console.log('[Testimonial] Left arrow not found!');
    }

    if (testimRightArrow) {
      testimRightArrow.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        console.log('[Testimonial] Right arrow clicked, current slide:', currentSlide);
        clearTimeout(testimTimer);
        playSlide(currentSlide += 1);
      });
      console.log('[Testimonial] Right arrow listener attached');
    } else {
      console.log('[Testimonial] Right arrow not found!');
    }

    for (var l = 0; l < testimDots.length; l++) {
      testimDots[l].addEventListener("click", function () {
        playSlide(currentSlide = testimDots.indexOf(this));
      });
    }

    if (testim) {
      testim.addEventListener("touchstart", function (e) {
        touchStartPos = e.changedTouches[0].clientX;
      });

      testim.addEventListener("touchend", function (e) {
        touchEndPos = e.changedTouches[0].clientX;

        touchPosDiff = touchStartPos - touchEndPos;

        console.log(touchPosDiff);
        console.log(touchStartPos);
        console.log(touchEndPos);


        if (touchPosDiff > 0 + ignoreTouch && testimLeftArrow) {
          testimLeftArrow.click();
        } else if (touchPosDiff < 0 - ignoreTouch && testimRightArrow) {
          testimRightArrow.click();
        } else {
          return;
        }

      });
    }
  }
}

// Initialize testimonial script when DOM is ready or immediately if already loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTestimonialScript);
} else {
  initTestimonialScript();
}


// Initialize Google Translate
function googleTranslateElementInit() {
  new google.translate.TranslateElement({
    pageLanguage: 'en',
    includedLanguages: 'ar,as,awa,bn,bho,zh-CN,cs,dog,nl,en,fr,fr-CA,de,gu,hi,it,ja,kn,ks,kok,ko,mai,ms,ml,mr,mwr,mni,np,or,pa,pt,pt-BR,ru,sat,sd,es,sw,ta,te,tr,ur,vi,si,ne,tl,th,kk,uz',
    layout: google.translate.TranslateElement.InlineLayout.SIMPLE,
    autoDisplay: false
  }, 'google_translate_element');
}

// Custom language selection handler
document.addEventListener('DOMContentLoaded', function () {
  const languageLinks = document.querySelectorAll('.dropdown-content a');
  const dropbtn = document.querySelector('.dropbtn');
  
  // Only initialize if dropbtn exists (not all pages have language selector)
  if (!dropbtn) {
    return;
  }
  
  let currentLanguage = 'en'; // Default language

  // Store original texts
  const elementsToTranslate = document.querySelectorAll('[data-translate]');
  const originalTexts = new Map();
  elementsToTranslate.forEach(el => {
    originalTexts.set(el, el.textContent);
  });

  languageLinks.forEach(link => {
    link.addEventListener('click', function (e) {
      e.preventDefault();
      const lang = this.getAttribute('data-lang');
      const langName = this.textContent;

      // Update dropdown button text
      if (dropbtn) {
        dropbtn.textContent = langName;
      }
      currentLanguage = lang;

      // Reset to original text before new translation
      elementsToTranslate.forEach(el => {
        el.textContent = originalTexts.get(el);
      });

      // Wait for Google Translate to be ready
      setTimeout(() => {
        const translateSelect = document.querySelector('.goog-te-combo');
        if (translateSelect) {
          translateSelect.value = lang;
          translateSelect.dispatchEvent(new Event('change'));
        }
      }, 100); // Small delay to ensure reset completes
    });
  });
  // Monitor Google Translate changes
  const observer = new MutationObserver((mutations) => {
    // Ensure the dropdown shows the current language
    const selectedLang = document.querySelector(`.dropdown-content a[data-lang="${currentLanguage}"]`);
    if (selectedLang && dropbtn) {
      dropbtn.textContent = selectedLang.textContent;
    }
  });
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true
  });
  // Set initial language display
  if (dropbtn) {
    dropbtn.textContent = 'English';
  }
});


// Initialize Google Translate



// nav search


   /**
 * TopTeen Search Functionality
 * This script handles the search functionality for the TopTeen website
 */

document.addEventListener('DOMContentLoaded', function() {
  // Find all search toggle elements (support for both ID and class-based selectors)
  const searchToggles = document.querySelectorAll('.search-toggle, #searchToggle');
  const searchContainer = document.querySelector('.search-container');
  const searchInput = document.querySelector('.search-input');
  const searchClose = document.querySelector('.search-close');
  const searchBtn = document.querySelector('.search-btn');
  
  // Only initialize search if elements exist (not on login page)
  if (!searchContainer || !searchInput) {
    return;
  }
  const searchResults = document.querySelector('.search-results');

  // Check if search elements exist
  if (!searchContainer || searchToggles.length === 0) {
    console.warn('Search elements not found in the DOM');
    return;
  }

  // Sample career data (replace with your actual data source)
  const careerData = [
    { title: 'Software Developer', category: 'Information Technology', description: 'Design and develop software applications' },
    { title: 'Web Developer', category: 'Information Technology', description: 'Create and maintain websites' },
    { title: 'Data Scientist', category: 'Information Technology', description: 'Analyze and interpret complex data' },
    { title: 'Customer Service Representative', category: 'Business Management', description: 'Handle customer inquiries and complaints' },
    { title: 'Marketing Manager', category: 'Business Management', description: 'Develop marketing strategies' },
    { title: 'Human Resources Specialist', category: 'Human Services', description: 'Recruit and hire employees' },
    { title: 'Financial Analyst', category: 'Finance', description: 'Analyze financial data and trends' },
    { title: 'Nurse', category: 'Healthcare', description: 'Provide patient care' },
    { title: 'Teacher', category: 'Education', description: 'Educate students in various subjects' }
  ];

  // Debounce function to limit how often a function can run
  function debounce(func, wait) {
    let timeout;
    return function(...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }

  // Toggle search container visibility
  function toggleSearch(e) {
    e.preventDefault();
    console.log('Search toggle clicked'); // Debug log
    searchContainer.classList.toggle('active');
    if (searchContainer.classList.contains('active')) {
      searchInput.focus();
    }
  }

  // Add click event to all search toggle elements
  searchToggles.forEach(toggle => {
    toggle.addEventListener('click', toggleSearch);
  });

  // Close search when clicking outside
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.search-container') && 
        !Array.from(searchToggles).some(toggle => toggle.contains(e.target))) {
      searchContainer.classList.remove('active');
    }
  });

  // Close search with close button
  if (searchClose) {
    searchClose.addEventListener('click', function() {
      searchContainer.classList.remove('active');
    });
  }

  // Handle search input
  const performSearch = debounce(function() {
    const query = searchInput.value.toLowerCase().trim();
    
    if (query.length < 2) {
      searchResults.innerHTML = '';
      return;
    }
    
    const filteredResults = careerData.filter(career => 
      career.title.toLowerCase().includes(query) ||
      career.category.toLowerCase().includes(query) ||
      career.description.toLowerCase().includes(query)
    );
    
    displayResults(filteredResults);
  }, 300);

  if (searchInput) {
    searchInput.addEventListener('input', performSearch);
  }

  if (searchBtn) {
    searchBtn.addEventListener('click', function(e) {
      e.preventDefault();
      performSearch();
    });
  }

  // Display search results
  function displayResults(results) {
    if (!searchResults) return;
    
    searchResults.innerHTML = '';
    
    if (results.length === 0) {
      searchResults.innerHTML = '<div class="p-3 text-center"><i class="bx bx-search-alt-2"></i> No results found</div>';
      return;
    }
    
    results.forEach(result => {
      const resultItem = document.createElement('div');
      resultItem.className = 'search-result-item';
      resultItem.innerHTML = `
        <h4>${result.title}</h4>
        <p><span class="badge bg-blue text-white">${result.category}</span> ${result.description}</p>
      `;
      
      resultItem.addEventListener('click', function() {
        // Navigate to career details page or show modal
        alert(`You selected: ${result.title}`);
        // Example: window.location.href = `/careers/${result.title.toLowerCase().replace(/\s+/g, '-')}`;
      });
      
      searchResults.appendChild(resultItem);
    });
  }

  // Log initialization success
  console.log('Search functionality initialized');
});

// nav search








