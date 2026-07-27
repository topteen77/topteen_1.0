

// Chat bot


//const API_URL = `https://43.204.127.118:8001/`;
// const API_URL = `http://demo.topteen.in/bot/`;

// Chat bot
// NOTE: Chatbot markup is not present on some pages (e.g. login pages where chatbot is disabled).
// Guard initialization to avoid JS runtime errors that break other page scripts.
// if (document.querySelector("#chatbot-toggler")) {
// let API_URL;
// if (window.location.hostname === "http://localhost/topteen/") {
//   API_URL = "http://demo.topteen.in/bot/";
// } else {
//   API_URL = "https://demo.topteen.in/bot/";
// }

// const chatBody = document.querySelector(".chat-body");
// const messageInput = document.querySelector(".message-input");
// const sendMessage = document.querySelector("#send-message");
// const fileInput = document.querySelector("#file-input");
// const fileUploadWrapper = document.querySelector(".file-upload-wrapper");
// const fileCancelButton = fileUploadWrapper.querySelector("#file-cancel");
// const chatbotToggler = document.querySelector("#chatbot-toggler");
// const closeChatbot = document.querySelector("#close-chatbot");

// // Generate a random UUID
// function uuidv4() {
//   return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'
//     .replace(/[xy]/g, function (c) {
//       const r = Math.random() * 16 | 0,
//         v = c == 'x' ? r : (r & 0x3 | 0x8);
//       return v.toString(16);
//     });
// }

// const unique_session_id = uuidv4();

// // Function to check if the browser is closing
// window.addEventListener('beforeunload', (event) => {
//   fetch(API_URL, {
//     method: 'POST',
//     headers: { 'Content-Type': 'application/json' },
//     body: JSON.stringify({
//       uuid: unique_session_id,
//       is_left: true
//     }),
//   });
// });

// // Function to track user inactivity
// let lastActivityTime = Date.now();
// const inactivityTimeout = 600000; // 10 minutes in milliseconds

// function trackInactivity() {
//   const currentTime = Date.now();
//   const timeElapsed = currentTime - lastActivityTime;

//   if (timeElapsed > inactivityTimeout) {
//     fetch(API_URL, {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify({
//         uuid: unique_session_id,
//         is_left: true
//       }),
//     });
//   }
//   lastActivityTime = currentTime;
// }

// document.addEventListener('mousemove', trackInactivity);
// document.addEventListener('keydown', trackInactivity);
// document.addEventListener('scroll', trackInactivity);
// document.addEventListener('click', trackInactivity);
// setInterval(trackInactivity, 10000);

// // API setup
// const userData = {
//   message: null,
//   file: {
//     data: null,
//     mime_type: null,
//   },
// };

// const chatHistory = [];
// const initialInputHeight = messageInput.scrollHeight;

// const createMessageElement = (content, ...classes) => {
//   const div = document.createElement("div");
//   div.classList.add("message", ...classes);
//   div.innerHTML = content;
//   return div;
// };

// const generateBotResponse = async (incomingMessageDiv) => {
//   const messageElement = incomingMessageDiv.querySelector(".message-text");
//   chatHistory.push({
//     role: "user",
//     parts: [{ text: userData.message }, ...(userData.file.data ? [{ inline_data: userData.file }] : [])],
//   });

//   const requestOptions = {
//     method: "POST",
//     headers: { "Content-Type": "application/json" },
//     body: JSON.stringify({
//       user: userData.message,
//       uuid: unique_session_id
//     }),
//   };

//   try {
//     const response = await fetch(API_URL, requestOptions);
//     const data = await response.json();
//     if (!response.ok) throw new Error(data.error.message);
//     const apiResponseText = data['AI'];
//     messageElement.innerHTML = apiResponseText;
//     chatHistory.push({
//       role: "model",
//       parts: [{ text: apiResponseText }],
//     });
//   } catch (error) {
//     console.log(error);
//     messageElement.innerText = error.message;
//     messageElement.style.color = "#ff0000";
//   } finally {
//     userData.file = {};
//     incomingMessageDiv.classList.remove("thinking");
//     chatBody.scrollTo({ top: chatBody.scrollHeight, behavior: "smooth" });
//   }
// };

// const handleOutgoingMessage = (e) => {
//   e.preventDefault();
//   userData.message = messageInput.value.trim();
//   messageInput.value = "";
//   messageInput.dispatchEvent(new Event("input"));
//   fileUploadWrapper.classList.remove("file-uploaded");

//   const messageContent = `
//         <div class="message-text"></div>
//         ${userData.file.data ? `<img src="data:${userData.file.mime_type};base64,${userData.file.data}" class="attachment" />` : ""}
//     `;
//   const outgoingMessageDiv = createMessageElement(messageContent, "user-message");
//   outgoingMessageDiv.querySelector(".message-text").innerText = userData.message;
//   chatBody.appendChild(outgoingMessageDiv);
//   chatBody.scrollTo({ top: chatBody.scrollHeight, behavior: "smooth" });

//   setTimeout(() => {
//     const messageContent = `
//             <svg class="bot-avatar" xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 1024 1024">
//                 <path d="M738.3 287.6H285.7c-59 0-106.8 47.8-106.8 106.8v303.1c0 59 47.8 106.8 106.8 106.8h81.5v111.1c0 .7.8 1.1 1.4.7l166.9-110.6 41.8-.8h117.4l43.6-.4c59 0 106.8-47.8 106.8-106.8V394.5c0-59-47.8-106.9-106.8-106.9zM351.7 448.2c0-29.5 23.9-53.5 53.5-53.5s53.5 23.9 53.5 53.5-23.9 53.5-53.5 53.5-53.5-23.9-53.5-53.5zm157.9 267.1c-67.8 0-123.8-47.5-132.3-109h264.6c-8.6 61.5-64.5 109-132.3 109zm110-213.7c-29.5 0-53.5-23.9-53.5-53.5s23.9-53.5 53.5-53.5 53.5 23.9 53.5 53.5-23.9 53.5-53.5 53.5zM867.2 644.5V453.1h26.5c19.4 0 35.1 15.7 35.1 35.1v121.1c0 19.4-15.7 35.1-35.1 35.1h-26.5zM95.2 609.4V488.2c0-19.4 15.7-35.1 35.1-35.1h26.5v191.3h-26.5c-19.4 0-35.1-15.7-35.1-35.1zM561.5 149.6c0 23.4-15.6 43.3-36.9 49.7v44.9h-30v-44.9c-21.4-6.5-36.9-26.3-36.9-49.7 0-28.6 23.3-51.9 51.9-51.9s51.9 23.3 51.9 51.9z"/>
//             </svg>
//             <div class="message-text">
//                 <div class="thinking-indicator flex items-center">
//                     <div class="fs-14 fw-normal me-2 shine-text py-0" id="word"></div>
//                     <div class="dot"></div>
//                     <div class="dot"></div>
//                     <div class="dot"></div>
//                 </div>
//             </div>
//         `;
//     const incomingMessageDiv = createMessageElement(messageContent, "bot-message", "thinking");
//     chatBody.appendChild(incomingMessageDiv);
//     chatBody.scrollTo({ top: chatBody.scrollHeight, behavior: "smooth" });
//     initWordAnimation();
//     generateBotResponse(incomingMessageDiv);
//   }, 600);
// };

// // Show AI message after 2 seconds - DISABLED: Now handled by chatbot.js auto-open functionality
// // setTimeout(() => {
// //   document.querySelector('.ai-chat-message').classList.add('show');
// // }, 4000);

// // Handle Let's Chat button click - with null check
// const letsChatBtn = document.querySelector('.lest-chart-sart');
// if (letsChatBtn) {
//   letsChatBtn.addEventListener('click', (e) => {
//     e.preventDefault();
//     const aiMessage = document.querySelector('.ai-chat-message');
//     if (aiMessage) aiMessage.style.display = 'none';
//     document.body.classList.add('show-chatbot');
//   });
// }

// // Add close functionality for the close button - with null check
// const closeIcon = document.querySelector('.ai-chat-message .close-icon');
// if (closeIcon) {
//   closeIcon.addEventListener('click', (e) => {
//     e.stopPropagation();
//     const aiMessage = document.querySelector('.ai-chat-message');
//     if (aiMessage) aiMessage.style.display = 'none';
//   });
// }

// // Hide AI message when chatbot is opened through toggler - with null check
// if (chatbotToggler) {
//   chatbotToggler.addEventListener('click', () => {
//     const aiMessage = document.querySelector('.ai-chat-message');
//     if (aiMessage) aiMessage.style.display = 'none';
//   });
// }

// // Initialize word animation
// const initWordAnimation = () => {
//   let count = -1;
//   const wordElement = document.getElementById('word');
//   const initText = "Thinking... Give me a sec!";
//   const wordsArray = [
//     " Processing your request",
//     " Working on it! One moment",
//     " Typing",
//     " Typing"
//   ];
//   wordElement.textContent = initText;

//   setInterval(() => {
//     count++;
//     wordElement.style.opacity = '0';
//     setTimeout(() => {
//       wordElement.textContent = wordsArray[count % wordsArray.length];
//       wordElement.style.opacity = '1';
//     }, 400);
//   }, 5500);
// };

// // Adjust input field height dynamically
// messageInput.addEventListener("input", () => {
//   messageInput.style.height = `${initialInputHeight}px`;
//   messageInput.style.height = `${messageInput.scrollHeight}px`;
//   document.querySelector(".chat-form").style.borderRadius = messageInput.scrollHeight > initialInputHeight ? "15px" : "32px";
// });

// // Handle Enter key press for sending messages
// messageInput.addEventListener("keydown", (e) => {
//   const userMessage = e.target.value.trim();
//   if (e.key === "Enter" && !e.shiftKey && userMessage && window.innerWidth > 768) {
//     handleOutgoingMessage(e);
//   }
// });

// // Handle file input change and preview the selected file
// fileInput.addEventListener("change", () => {
//   const file = fileInput.files[0];
//   if (!file) return;

//   const reader = new FileReader();
//   reader.onload = (e) => {
//     fileInput.value = "";
//     fileUploadWrapper.querySelector("img").src = e.target.result;
//     fileUploadWrapper.classList.add("file-uploaded");
//     const base64String = e.target.result.split(",")[1];
//     userData.file = {
//       data: base64String,
//       mime_type: file.type,
//     };
//   };
//   reader.readAsDataURL(file);
// });

// // Cancel file upload
// fileCancelButton.addEventListener("click", () => {
//   userData.file = {};
//   fileUploadWrapper.classList.remove("file-uploaded");
// });

// // Initialize emoji picker and handle emoji selection
// const picker = new EmojiMart.Picker({
//   theme: "light",
//   skinTonePosition: "none",
//   previewPosition: "none",
//   onEmojiSelect: (emoji) => {
//     const { selectionStart: start, selectionEnd: end } = messageInput;
//     messageInput.setRangeText(emoji.native, start, end, "end");
//     messageInput.focus();
//   },
//   onClickOutside: (e) => {
//     if (e.target.id === "emoji-picker") {
//       document.body.classList.toggle("show-emoji-picker");
//     } else {
//       document.body.classList.remove("show-emoji-picker");
//     }
//   },
// });

// document.querySelector(".chat-form").appendChild(picker);

// sendMessage.addEventListener("click", (e) => handleOutgoingMessage(e));
// document.querySelector("#file-upload").addEventListener("click", () => fileInput.click());
// closeChatbot.addEventListener("click", () => document.body.classList.remove("show-chatbot"));
// chatbotToggler.addEventListener("click", () => document.body.classList.toggle("show-chatbot"));

// } // end chatbot guard


// Close chatbot when clicking outside of it

// Enquiry source tracking fallback:
// If URL has ?ref=TOKEN, ping backend on page load to ensure the hit is recorded.
// Token is stored in sessionStorage so SPA-style navigations in same tab can still attribute.
(function enquiryRefTrackingInit() {
  function getCookie(name) {
    const nameEq = `${name}=`;
    const parts = document.cookie ? document.cookie.split(";") : [];
    for (let i = 0; i < parts.length; i += 1) {
      const c = parts[i].trim();
      if (c.indexOf(nameEq) === 0) return decodeURIComponent(c.substring(nameEq.length));
    }
    return "";
  }

  function setCookie(name, value) {
    // 1 day persistence is enough for attribution continuity.
    document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=86400; samesite=lax`;
  }

  let ref = "";
  try {
    const url = new URL(window.location.href);
    ref = (url.searchParams.get("ref") || "").trim();
  } catch (e) {
    ref = "";
  }

  const key = "tt_ref_token";
  let token = ref;

  if (ref) {
    try { sessionStorage.setItem(key, ref); } catch (e) { /* no-op */ }
    try { localStorage.setItem(key, ref); } catch (e) { /* no-op */ }
    try { setCookie(key, ref); } catch (e) { /* no-op */ }
  } else {
    try { token = (sessionStorage.getItem(key) || "").trim(); } catch (e) { /* no-op */ }
    if (!token) {
      try { token = (localStorage.getItem(key) || "").trim(); } catch (e) { /* no-op */ }
    }
    if (!token) {
      try { token = (getCookie(key) || "").trim(); } catch (e) { /* no-op */ }
    }
  }

  if (!token) return;

  const endpoint = `/entry/attribution/?ref=${encodeURIComponent(token)}&path=${encodeURIComponent(window.location.pathname)}&title=${encodeURIComponent(document.title || "")}`;
  fetch(endpoint, {
    method: "GET",
    credentials: "same-origin",
    keepalive: true,
    headers: { "X-Requested-With": "XMLHttpRequest" },
  }).catch(() => { /* no-op */ });
})();


// header fixed //
const header = document.querySelector('.header');
if (header) {
  window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
      header.classList.add('shrink');
    } else {
      header.classList.remove('shrink');
    }
  });
}





// Mobile nav toggle is handled in template20/includes/header.html (avoid duplicate handlers).

// Toggle to show and hide dropdown menu
const dropdown = document.querySelectorAll(".dropdown");

dropdown.forEach((item) => {
  const dropdownToggle = item.querySelector(".dropdown-toggle");

  // Some dropdown-like wrappers (e.g. notifications bell) use Bootstrap and do not have
  // our custom `.dropdown-toggle` element. Avoid crashing the rest of the JS.
  if (!dropdownToggle) return;

  // Bootstrap-managed menus use `.dropdown-menu`; legacy header menus use `.dropdown-content`.
  // Do not bind the legacy toggle handler when only Bootstrap markup is present (v2 shell topbar).
  const legacyMenu = item.querySelector(".dropdown-content");
  const bsMenu = item.querySelector(".dropdown-menu");
  if (bsMenu && !legacyMenu) return;

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
  if (!dropdownContent) return;

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

// v2 dashboard topbar: delay-hide avatar dropdown on hover-out
// (Institute/marketing/group dashboards use this shared script; counselor has its own.)
(function () {
  var CLOSE_DELAY_MS = 6000;
  var timer = null;

  function clearT() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function closeNow(wrap) {
    try {
      if (!wrap || !wrap.classList.contains("dropdown-show")) return;
      var dd = wrap.querySelector(".dropdown-content");
      if (dd) dd.removeAttribute("style");
      wrap.classList.remove("dropdown-show");
    } catch (e) {}
  }

  function scheduleClose(wrap) {
    clearT();
    timer = setTimeout(function () {
      closeNow(wrap);
    }, CLOSE_DELAY_MS);
  }

  function bindOnce() {
    var wrap = document.querySelector(".ttv2-topbar-avatar-dropdown.dropdown");
    if (!wrap || wrap.getAttribute("data-ttv2-hoverbound") === "1") return;
    wrap.setAttribute("data-ttv2-hoverbound", "1");

    var menu = wrap.querySelector(".dropdown-content");
    wrap.addEventListener("mouseenter", function () {
      clearT();
    });
    wrap.addEventListener("mouseleave", function () {
      scheduleClose(wrap);
    });
    if (menu) {
      menu.addEventListener("mouseenter", function () {
        clearT();
      });
      menu.addEventListener("mouseleave", function () {
        scheduleClose(wrap);
      });
    }

    // If opened and user scrolls away, still close quickly.
    window.addEventListener(
      "scroll",
      function () {
        // keep the delay behavior; don't instant-close on minor scroll
        if (wrap.classList.contains("dropdown-show")) scheduleClose(wrap);
      },
      { passive: true }
    );
  }

  document.addEventListener("DOMContentLoaded", bindOnce);
  // In case scripts run after DOMContentLoaded in some shells
  try {
    bindOnce();
  } catch (e) {}
})();

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

// scrolling js //
function initScrollerAnimation() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const scrollers = document.querySelectorAll(".scroller");
  if (!scrollers.length) return;

  scrollers.forEach((scroller) => {
    // Prevent duplicate clones if this initializer runs again.
    if (scroller.getAttribute("data-animated") === "true") return;

    const scrollerInner = scroller.querySelector(".scroller__inner");
    if (!scrollerInner) return;

    scroller.setAttribute("data-animated", "true");
    const scrollerContent = Array.from(scrollerInner.children);

    scrollerContent.forEach((item) => {
      const duplicatedItem = item.cloneNode(true);
      duplicatedItem.setAttribute("aria-hidden", "true");
      scrollerInner.appendChild(duplicatedItem);
    });
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initScrollerAnimation);
} else {
  initScrollerAnimation();
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

// Run on page load - lazily generate video thumbnails when videos enter the viewport
window.addEventListener("load", () => {
  const videos = document.querySelectorAll(".videoPlayer");
  const canvases = document.querySelectorAll(".thumbnailCanvas");

  if (videos.length === 0 || canvases.length === 0) {
    return;
  }

  // Fallback for older browsers: generate all thumbnails at once (previous behavior)
  if (!("IntersectionObserver" in window)) {
    console.log("IntersectionObserver not supported, generating all thumbnails on load...");
    generateThumbnails();
    return;
  }

  if (videos.length !== canvases.length) {
    console.error("Mismatch between videos and canvases");
    return;
  }

  const observer = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const video = entry.target;
        const index = Array.prototype.indexOf.call(videos, video);
        if (index === -1) return;
        const canvas = canvases[index];
        // Only load and capture thumbnail once the video is actually near/in view
        captureThumbnail(video, canvas);
        obs.unobserve(video);
      });
    },
    {
      root: null,
      threshold: 0.25,
    }
  );

  videos.forEach((video) => observer.observe(video));
});

// OWL CAROUSEL //
$(document).ready(function ($) {
  if (typeof $.fn.owlCarousel !== 'function') {
    return;
  }

  // PSYCHOMETRIC TEST CAROUSEL //
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

  function syncAboutCarouselNav($carousel, $prevBtn, $nextBtn) {
    if (!$carousel.length || !$prevBtn.length || !$nextBtn.length) return;
    var $nav = $carousel.find('.owl-nav');
    if ($nav.find('.owl-prev').hasClass('disabled')) {
      $prevBtn.addClass('disabled');
    } else {
      $prevBtn.removeClass('disabled');
    }
    if ($nav.find('.owl-next').hasClass('disabled')) {
      $nextBtn.addClass('disabled');
    } else {
      $nextBtn.removeClass('disabled');
    }
  }

  $('.about-test-carousels').each(function () {
    var $section = $(this);
    var $carousel = $section.find('.owl-carousel').first();
    var $controls = $section.nextAll('.d-flex.justify-content-center').first().find('.btn-wrap');
    if (!$carousel.length || !$controls.length) return;

    var $prevBtn = $controls.find('.prev-btn');
    var $nextBtn = $controls.find('.next-btn');

    $nextBtn.on('click', function () {
      $carousel.trigger('next.owl.carousel');
    });
    $prevBtn.on('click', function () {
      $carousel.trigger('prev.owl.carousel');
    });

    syncAboutCarouselNav($carousel, $prevBtn, $nextBtn);
    $carousel.on('translated.owl.carousel', function () {
      syncAboutCarouselNav($carousel, $prevBtn, $nextBtn);
    });
  });

  $('button[data-bs-toggle="pill"]').on('shown.bs.tab', function (event) {
    var target = event.target.getAttribute('data-bs-target');
    if (!target) return;
    $(target).find('.owl-carousel.owl-loaded').trigger('refresh.owl.carousel');
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


// Initialize Google Translate — centralized show/hide language widget
var ttLanguageWidgetReady = false;
window.TT_INCLUDED_LANGUAGES = window.TT_INCLUDED_LANGUAGES || 'ar,as,awa,bn,bho,zh-CN,cs,dog,nl,en,fr,fr-CA,de,el,gu,hi,it,ja,kn,ks,kok,ko,mai,ms,ml,mr,mwr,mni,np,or,pa,pt,pt-BR,ru,sat,sd,es,sw,ta,te,tr,ur,vi,si,ne,tl,th,kk,uz';
window.TT_TRANSLATE_COMPLEXITY_ENABLED = window.TT_TRANSLATE_COMPLEXITY_ENABLED !== false;
window.TT_TRANSLATE_COMPLEXITY_API = window.TT_TRANSLATE_COMPLEXITY_API || '/api/translate-complexity/';

var TT_COMPLEXITY_STORAGE_KEY = 'tt_translate_complexity';
var TT_COMPLEXITY_HINTS = {
  easy: 'Easy uses simple everyday words — best for younger students.',
  medium: 'Medium keeps a balanced, clear tone.',
  hard: 'Hard uses formal, academic language.'
};
var TT_LANG_WIDGET_COPY = {
  title: 'Choose language',
  searchPlaceholder: 'Search',
  searchAria: 'Search language',
  resetTitle: 'Reset to English',
  resetAria: 'Reset to English',
  closeAria: 'Close language menu',
  complexityLabel: 'Reading level',
  easy: 'Easy',
  medium: 'Medium',
  hard: 'Hard',
  loaderTitle: 'Switching language',
  loaderSub: 'Updating page content…'
};
var TT_CONTENT_ROOT_SELECTORS = ['main', '[role="main"]', '#content', '.main-content'];
var TT_CONTENT_TEXT_SELECTORS = 'p, h1, h2, h3, h4, h5, h6, li, td, th, dt, dd, label, figcaption, blockquote, .card-text, .report-text';
var TT_SKIP_ANCESTOR_SELECTORS = '#tt-language-widget, #tt-lang-switch-loader, header, footer, nav, script, style, noscript, .goog-te-banner-frame, .skiptranslate, .tt-lang-widget, .modal, [data-tt-lang-trigger]';

function getTranslateComplexity() {
  try {
    var stored = window.localStorage.getItem(TT_COMPLEXITY_STORAGE_KEY);
    if (stored === 'easy' || stored === 'medium' || stored === 'hard') {
      return stored;
    }
  } catch (e) {}
  return 'easy';
}

function setTranslateComplexity(level) {
  try {
    window.localStorage.setItem(TT_COMPLEXITY_STORAGE_KEY, level);
  } catch (e) {}
}

function getCsrfToken() {
  var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

function getPageContentRoot() {
  var index;
  for (index = 0; index < TT_CONTENT_ROOT_SELECTORS.length; index += 1) {
    var node = document.querySelector(TT_CONTENT_ROOT_SELECTORS[index]);
    if (node) {
      return node;
    }
  }
  return document.body;
}

function shouldSkipTranslatedNode(node) {
  if (!node || !node.closest) {
    return true;
  }
  return !!node.closest(TT_SKIP_ANCESTOR_SELECTORS);
}

function collectTranslatableElements(root) {
  var seen = new Set();
  var elements = [];
  root.querySelectorAll(TT_CONTENT_TEXT_SELECTORS).forEach(function (el) {
    if (seen.has(el) || shouldSkipTranslatedNode(el)) {
      return;
    }
    var text = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (text.length < 20) {
      return;
    }
    seen.add(el);
    elements.push({ el: el, text: text });
  });
  return elements;
}

function chunkArray(items, size) {
  var chunks = [];
  var index;
  for (index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}

function showTranslateComplexityStatus(message, isError) {
  var existing = document.getElementById('tt-translate-complexity-status');
  if (existing) {
    existing.remove();
  }
  var toast = document.createElement('div');
  toast.id = 'tt-translate-complexity-status';
  toast.className = 'tt-translate-complexity-status' + (isError ? ' is-error' : '');
  toast.textContent = message;
  document.body.appendChild(toast);
  window.setTimeout(function () {
    if (toast.parentNode) {
      toast.parentNode.removeChild(toast);
    }
  }, 3200);
}

var ttComplexityRequestToken = 0;

function parseTranslateComplexityResponse(response) {
  return response.text().then(function (raw) {
    var text = (raw || '').trim();
    if (!text) {
      return { ok: false, error: 'Empty response from reading-level service' };
    }
    // HTML login/error pages start with "<" — never pass them to JSON.parse.
    if (text.charAt(0) === '<') {
      return {
        ok: false,
        error: response.status === 401 || response.status === 403
          ? 'Session expired — refresh and try again'
          : 'Reading-level service returned an HTML error page'
      };
    }
    try {
      return JSON.parse(text);
    } catch (err) {
      return {
        ok: false,
        error: 'Reading-level service returned invalid JSON'
      };
    }
  });
}

function applyTranslateComplexity(langCode, level) {
  if (!window.TT_TRANSLATE_COMPLEXITY_ENABLED || !langCode || langCode === 'en') {
    return Promise.resolve();
  }
  if (level === 'medium') {
    return Promise.resolve();
  }

  var requestToken = ++ttComplexityRequestToken;
  var root = getPageContentRoot();
  var items = collectTranslatableElements(root);
  if (!items.length) {
    return Promise.resolve();
  }

  showTranslateComplexityStatus('Adjusting reading level…', false);

  var batches = chunkArray(items, 20);
  var chain = Promise.resolve();
  var appliedAny = false;
  var softFail = false;
  var cacheHitsTotal = 0;
  var cacheMissesTotal = 0;
  var llmCallsTotal = 0;
  var storedTotal = 0;

  batches.forEach(function (batch) {
    chain = chain.then(function () {
      if (requestToken !== ttComplexityRequestToken) {
        return;
      }
      return fetch(window.TT_TRANSLATE_COMPLEXITY_API, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
          texts: batch.map(function (item) { return item.text; }),
          target_lang: langCode,
          level: level
        })
      }).then(function (response) {
        return parseTranslateComplexityResponse(response).then(function (payload) {
          if (requestToken !== ttComplexityRequestToken) {
            return;
          }
          if (!response.ok || !payload || !payload.ok || !Array.isArray(payload.texts)) {
            // Keep Google Translate text; do not surface raw JSON.parse errors.
            softFail = true;
            return;
          }
          var cacheInfo = payload.cache || {};
          cacheHitsTotal += Number(cacheInfo.cache_hits || 0);
          cacheMissesTotal += Number(cacheInfo.cache_misses || 0);
          llmCallsTotal += Number(cacheInfo.llm_calls || 0);
          storedTotal += Number(cacheInfo.stored || 0);

          if (cacheInfo.from_cache || (cacheInfo.cache_hits > 0 && !cacheInfo.cache_misses)) {
            console.log(
              '[TopTeen translate] read from cache — hits:',
              cacheInfo.cache_hits,
              'lang:',
              langCode,
              'level:',
              level
            );
          } else if (cacheInfo.cache_hits > 0) {
            console.log(
              '[TopTeen translate] partial cache — hits:',
              cacheInfo.cache_hits,
              'misses:',
              cacheInfo.cache_misses,
              'llm_calls:',
              cacheInfo.llm_calls,
              'stored:',
              cacheInfo.stored
            );
          } else if (cacheInfo.llm_calls > 0) {
            console.log(
              '[TopTeen translate] LLM call — misses:',
              cacheInfo.cache_misses,
              'stored to Redis:',
              cacheInfo.stored
            );
          }

          payload.texts.forEach(function (value, index) {
            if (value && batch[index] && batch[index].el) {
              batch[index].el.textContent = value;
              appliedAny = true;
            }
          });
        });
      }).catch(function () {
        softFail = true;
      });
    });
  });

  return chain.then(function () {
    if (requestToken !== ttComplexityRequestToken) {
      return;
    }
    if (cacheHitsTotal || cacheMissesTotal || llmCallsTotal) {
      console.log(
        '[TopTeen translate] summary — from cache:',
        cacheHitsTotal,
        '| LLM misses:',
        cacheMissesTotal,
        '| llm_calls:',
        llmCallsTotal,
        '| stored:',
        storedTotal
      );
    }
    if (appliedAny) {
      var label = level.charAt(0).toUpperCase() + level.slice(1);
      var statusMsg = label + ' reading level applied';
      if (cacheHitsTotal > 0 && cacheMissesTotal === 0) {
        statusMsg += ' (from cache)';
      }
      showTranslateComplexityStatus(statusMsg, false);
    } else if (softFail) {
      // Silent: language translation still works via Google Translate.
      showTranslateComplexityStatus('Using standard translation', false);
    }
  });
}

function scheduleTranslateComplexity(langCode, level, delayMs) {
  window.clearTimeout(window._ttComplexityTimer);
  window._ttComplexityTimer = window.setTimeout(function () {
    applyTranslateComplexity(langCode, level);
  }, delayMs || 1800);
}

function getIncludedLanguages() {
  return window.TT_INCLUDED_LANGUAGES || 'en';
}

function googleTranslateElementInit() {
  new google.translate.TranslateElement({
    pageLanguage: 'en',
    includedLanguages: getIncludedLanguages(),
    layout: google.translate.TranslateElement.InlineLayout.HORIZONTAL,
    autoDisplay: false
  }, 'google_translate_element');
  initCustomLanguageSelector();
}

function initCustomLanguageSelector() {
  var widget = document.getElementById('tt-language-widget');
  if (!widget) {
    return;
  }

  // Escape popup + triggers from Google Translate so names stay English.
  widget.classList.add('notranslate', 'skiptranslate');
  widget.setAttribute('translate', 'no');

  var grid = document.getElementById('tt-lang-grid');
  var searchInput = document.getElementById('tt-lang-search');
  var resetBtn = widget.querySelector('[data-tt-lang-reset]');
  var complexityWrap = document.getElementById('tt-lang-complexity-wrap');
  var complexityHint = document.getElementById('tt-lang-complexity-hint');
  var complexityButtons = complexityWrap
    ? complexityWrap.querySelectorAll('[data-complexity]')
    : [];
  var langLoader = document.getElementById('tt-lang-switch-loader');
  var currentLanguage = 'en';
  var currentComplexity = getTranslateComplexity();
  var isOpen = false;
  var langSwitchToken = 0;
  var langSwitchObserver = null;

  function getTranslateCombo() {
    var container = document.getElementById('google_translate_element');
    if (container) {
      return container.querySelector('.goog-te-combo');
    }
    return document.querySelector('.goog-te-combo');
  }

  function getTriggers() {
    return document.querySelectorAll('[data-tt-lang-trigger]');
  }

  function protectTriggersFromTranslate() {
    getTriggers().forEach(function (trigger) {
      trigger.classList.add('notranslate', 'skiptranslate');
      trigger.setAttribute('translate', 'no');
    });
  }

  function restoreWidgetEnglishCopy() {
    var title = document.getElementById('tt-lang-widget-title');
    if (title) {
      title.textContent = TT_LANG_WIDGET_COPY.title;
    }
    if (searchInput) {
      searchInput.placeholder = TT_LANG_WIDGET_COPY.searchPlaceholder;
      searchInput.setAttribute('aria-label', TT_LANG_WIDGET_COPY.searchAria);
    }
    if (resetBtn) {
      resetBtn.setAttribute('aria-label', TT_LANG_WIDGET_COPY.resetAria);
      resetBtn.setAttribute('title', TT_LANG_WIDGET_COPY.resetTitle);
    }
    var closeBtn = widget.querySelector('.tt-lang-close');
    if (closeBtn) {
      closeBtn.setAttribute('aria-label', TT_LANG_WIDGET_COPY.closeAria);
    }
    var complexityLabel = document.getElementById('tt-lang-complexity-label');
    if (complexityLabel) {
      complexityLabel.textContent = TT_LANG_WIDGET_COPY.complexityLabel;
    }
    complexityButtons.forEach(function (btn) {
      var level = btn.getAttribute('data-complexity');
      if (level && TT_LANG_WIDGET_COPY[level]) {
        btn.textContent = TT_LANG_WIDGET_COPY[level];
      }
    });
    if (complexityHint) {
      complexityHint.textContent = TT_COMPLEXITY_HINTS[currentComplexity] || '';
    }
    if (grid) {
      grid.querySelectorAll('.tt-lang-option[data-lang-name]').forEach(function (btn) {
        btn.textContent = btn.getAttribute('data-lang-name') || btn.textContent;
      });
    }
  }

  function showLanguageSwitchLoader(langName) {
    if (!langLoader) {
      return;
    }
    var titleEl = document.getElementById('tt-lang-switch-loader-title');
    var subEl = document.getElementById('tt-lang-switch-loader-sub');
    if (titleEl) {
      titleEl.textContent = langName && langName !== 'English'
        ? ('Switching to ' + langName)
        : TT_LANG_WIDGET_COPY.loaderTitle;
    }
    if (subEl) {
      subEl.textContent = TT_LANG_WIDGET_COPY.loaderSub;
    }
    langLoader.hidden = false;
    langLoader.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(function () {
      langLoader.classList.add('is-visible');
    });
    document.body.classList.add('tt-lang-switching');
  }

  function hideLanguageSwitchLoader() {
    if (!langLoader) {
      return;
    }
    langLoader.classList.remove('is-visible');
    langLoader.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('tt-lang-switching');
    window.setTimeout(function () {
      if (!langLoader.classList.contains('is-visible')) {
        langLoader.hidden = true;
      }
    }, 220);
  }

  function waitForLanguageSwitchSettle(token, done) {
    if (langSwitchObserver) {
      langSwitchObserver.disconnect();
      langSwitchObserver = null;
    }
    var finished = false;
    var quietTimer = null;
    var startedAt = Date.now();
    var minMs = 900;
    var maxMs = 3800;

    function finish() {
      if (finished || token !== langSwitchToken) {
        return;
      }
      finished = true;
      if (quietTimer) {
        window.clearTimeout(quietTimer);
      }
      if (langSwitchObserver) {
        langSwitchObserver.disconnect();
        langSwitchObserver = null;
      }
      restoreWidgetEnglishCopy();
      if (typeof done === 'function') {
        done();
      }
    }

    function tryFinish() {
      if (finished || token !== langSwitchToken) {
        return;
      }
      var elapsed = Date.now() - startedAt;
      if (elapsed < minMs) {
        window.setTimeout(tryFinish, minMs - elapsed);
        return;
      }
      finish();
    }

    try {
      langSwitchObserver = new MutationObserver(function (mutations) {
        if (token !== langSwitchToken) {
          return;
        }
        // Ignore mutations inside the loader / language widget itself.
        var relevant = mutations.some(function (mutation) {
          var target = mutation.target;
          if (!target) {
            return false;
          }
          var el = target.nodeType === 1 ? target : target.parentElement;
          if (el && el.closest && el.closest('#tt-lang-switch-loader, #tt-language-widget')) {
            return false;
          }
          return true;
        });
        if (!relevant) {
          return;
        }
        window.clearTimeout(quietTimer);
        quietTimer = window.setTimeout(tryFinish, 500);
      });
      langSwitchObserver.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true
      });
    } catch (e) {
      window.setTimeout(finish, 1400);
      return;
    }

    // Cached translations may not mutate much — still show loader briefly.
    window.setTimeout(tryFinish, minMs + 250);
    window.setTimeout(finish, maxMs);
  }

  function setWidgetOpen(open) {
    var nextOpen = !!open;
    if (nextOpen === isOpen) {
      return;
    }
    isOpen = nextOpen;

    if (isOpen) {
      restoreWidgetEnglishCopy();
      widget.hidden = false;
      widget.setAttribute('aria-hidden', 'false');
      requestAnimationFrame(function () {
        widget.classList.add('is-open');
      });
      if (searchInput) {
        searchInput.value = '';
        filterLanguages('');
        window.setTimeout(function () {
          searchInput.focus();
        }, 320);
      }
    } else {
      widget.classList.remove('is-open');
      widget.setAttribute('aria-hidden', 'true');
      window.setTimeout(function () {
        if (!isOpen) {
          widget.hidden = true;
        }
      }, 320);
    }

    document.body.classList.toggle('tt-lang-menu-open', isOpen);
    getTriggers().forEach(function (trigger) {
      trigger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });
  }

  function updateTriggerLabels(langCode, langName) {
    protectTriggersFromTranslate();
    document.querySelectorAll('[data-tt-lang-trigger] .tt-lang-toggle-label').forEach(function (labelEl) {
      if (langCode === 'en') {
        labelEl.textContent = 'Language';
        return;
      }
      var levelLabel = currentComplexity.charAt(0).toUpperCase() + currentComplexity.slice(1);
      labelEl.textContent = langName + ' · ' + levelLabel;
    });
  }

  function updateComplexityUi() {
    if (!complexityWrap) {
      return;
    }
    var showComplexity = window.TT_TRANSLATE_COMPLEXITY_ENABLED && currentLanguage !== 'en';
    complexityWrap.hidden = !showComplexity;
    complexityButtons.forEach(function (btn) {
      var level = btn.getAttribute('data-complexity');
      var active = level === currentComplexity;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-checked', active ? 'true' : 'false');
    });
    if (complexityHint) {
      complexityHint.textContent = TT_COMPLEXITY_HINTS[currentComplexity] || '';
    }
  }

  function resolveLanguageName(langCode) {
    if (!langCode || langCode === 'en') {
      return 'English';
    }
    var resolved = langCode;
    getEnabledLanguageEntries().some(function (entry) {
      if (entry.code === langCode) {
        resolved = entry.name || langCode;
        return true;
      }
      return false;
    });
    return resolved;
  }

  function setComplexity(level, rerun) {
    if (level !== 'easy' && level !== 'medium' && level !== 'hard') {
      return;
    }
    currentComplexity = level;
    setTranslateComplexity(level);
    updateComplexityUi();
    updateTriggerLabels(currentLanguage, resolveLanguageName(currentLanguage));
    if (rerun && currentLanguage !== 'en') {
      scheduleTranslateComplexity(currentLanguage, currentComplexity, 300);
    }
  }

  function selectLanguage(langCode, langName) {
    if (!grid) {
      return;
    }
    var safeName = langName || resolveLanguageName(langCode);
    var combo = getTranslateCombo();
    var token = ++langSwitchToken;
    currentLanguage = langCode;
    showLanguageSwitchLoader(safeName);

    if (combo) {
      // Prefer Google combo when the language is supported there.
      var hasOption = Array.from(combo.options).some(function (option) {
        return option.value === langCode;
      });
      if (hasOption) {
        combo.value = langCode;
        combo.dispatchEvent(new Event('change'));
      } else {
        // Fallback for catalog languages Google omits from the combo.
        var hostname = window.location.hostname;
        document.cookie = 'googtrans=/en/' + langCode + '; path=/';
        document.cookie = 'googtrans=/en/' + langCode + '; path=/; domain=.' + hostname;
        window.location.reload();
        return;
      }
    }
    updateTriggerLabels(langCode, safeName);
    updateComplexityUi();
    // Rebuild so the newly selected language is hidden and the previous one reappears.
    buildLanguageOptions(combo);
    restoreWidgetEnglishCopy();
    setWidgetOpen(false);
    waitForLanguageSwitchSettle(token, hideLanguageSwitchLoader);
    if (langCode !== 'en') {
      scheduleTranslateComplexity(langCode, currentComplexity, 1800);
    } else {
      ttComplexityRequestToken += 1;
    }
  }

  function filterLanguages(query) {
    if (!grid) {
      return;
    }
    var normalized = query.trim().toLowerCase();
    grid.querySelectorAll('.tt-lang-option').forEach(function (btn) {
      var label = (
        (btn.getAttribute('data-lang-name') || '') + ' ' +
        (btn.getAttribute('data-lang') || '') + ' ' +
        (btn.textContent || '')
      ).toLowerCase();
      btn.hidden = normalized && label.indexOf(normalized) === -1;
    });
  }

  function resetLanguage() {
    var hostname = window.location.hostname;
    document.cookie = 'googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    document.cookie = 'googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=.' + hostname;
    selectLanguage('en', 'English');
  }

  function sortLanguageEntries(entries) {
    return entries.slice().sort(function (a, b) {
      if (a.code === 'en') {
        return -1;
      }
      if (b.code === 'en') {
        return 1;
      }
      return String(a.name || '').localeCompare(String(b.name || ''));
    });
  }

  function getEnabledLanguageEntries() {
    if (Array.isArray(window.TT_ENABLED_LANGUAGES) && window.TT_ENABLED_LANGUAGES.length) {
      return window.TT_ENABLED_LANGUAGES.map(function (entry) {
        return {
          code: entry.code,
          name: entry.name || entry.code
        };
      }).filter(function (entry) {
        return !!entry.code;
      });
    }
    // Fallback: codes from CSV + labels from Google combo when available.
    var combo = getTranslateCombo();
    var nameByCode = {};
    if (combo) {
      Array.from(combo.options).forEach(function (option) {
        if (option.value) {
          nameByCode[option.value] = option.value === 'en' ? 'English' : option.textContent.trim();
        }
      });
    }
    return String(getIncludedLanguages())
      .split(',')
      .map(function (code) { return code.trim(); })
      .filter(Boolean)
      .map(function (code) {
        return { code: code, name: nameByCode[code] || code };
      });
  }

  function buildLanguageOptions(combo) {
    if (!grid) {
      return;
    }
    grid.innerHTML = '';
    var selected = currentLanguage || 'en';
    var entries = sortLanguageEntries(
      getEnabledLanguageEntries().filter(function (entry) {
        // Show every enabled language except the currently selected one.
        return entry.code !== selected;
      })
    );
    entries.forEach(function (entry) {
      var langName = entry.code === 'en' ? 'English' : entry.name;
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'tt-lang-option notranslate';
      btn.setAttribute('translate', 'no');
      btn.setAttribute('data-lang', entry.code);
      btn.setAttribute('data-lang-name', langName);
      btn.setAttribute('role', 'option');
      btn.textContent = langName;
      btn.addEventListener('click', function () {
        selectLanguage(entry.code, langName);
      });
      grid.appendChild(btn);
    });
    var selectedName = resolveLanguageName(selected);
    updateTriggerLabels(selected, selectedName);
    restoreWidgetEnglishCopy();
    // Keep Google combo in sync when present (used to apply translation).
    if (combo && selected) {
      try {
        combo.value = selected;
      } catch (e) {
        /* ignore */
      }
    }
  }

  function bindWidgetShell() {
    if (widget.dataset.ttLangShellBound === '1') {
      return;
    }
    widget.dataset.ttLangShellBound = '1';

    function bindDirectTriggers() {
      getTriggers().forEach(function (trigger) {
        if (trigger.dataset.ttLangDirectBound === '1') {
          return;
        }
        trigger.dataset.ttLangDirectBound = '1';
        trigger.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          setWidgetOpen(!isOpen);
        });
      });
    }

    document.addEventListener('click', function (e) {
      if (e.target.closest('[data-tt-lang-trigger]')) {
        e.preventDefault();
        e.stopPropagation();
        setWidgetOpen(!isOpen);
        return;
      }
      if (e.target.closest('[data-tt-lang-close]')) {
        e.preventDefault();
        e.stopPropagation();
        setWidgetOpen(false);
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen) {
        setWidgetOpen(false);
      }
    });

    bindDirectTriggers();

    window.ttLanguageSelector = {
      open: function () { setWidgetOpen(true); },
      close: function () { setWidgetOpen(false); },
      toggle: function () { setWidgetOpen(!isOpen); },
      refreshTriggers: bindDirectTriggers
    };
  }

  function bindWidgetOptions() {
    if (widget.dataset.ttLangReady === '1') {
      return;
    }
    widget.dataset.ttLangReady = '1';
    ttLanguageWidgetReady = true;

    if (resetBtn) {
      resetBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        resetLanguage();
      });
    }

    complexityButtons.forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        setComplexity(btn.getAttribute('data-complexity'), true);
      });
    });

    setComplexity(currentComplexity, false);

    if (searchInput) {
      searchInput.addEventListener('input', function () {
        filterLanguages(searchInput.value);
      });
      searchInput.addEventListener('click', function (e) {
        e.stopPropagation();
      });
    }
  }

  function bindControls() {
    bindWidgetOptions();
  }

  function readCookieLanguage() {
    var match = document.cookie.match(/(?:^|;\s*)googtrans=([^;]+)/);
    if (!match) {
      return 'en';
    }
    var parts = decodeURIComponent(match[1]).split('/');
    return parts.length >= 3 ? parts[2] : 'en';
  }

  function waitForCombo(attempts) {
    if (widget.dataset.ttLangReady === '1') {
      return;
    }
    var combo = getTranslateCombo();
    var hasEnabledList = Array.isArray(window.TT_ENABLED_LANGUAGES) && window.TT_ENABLED_LANGUAGES.length > 0;
    var comboReady = combo && combo.options.length > 1;
    // Build from our enabled catalog as soon as possible; don't wait only on Google's combo
    // (Google often omits several enabled codes, which previously showed ~42 instead of 48).
    if (hasEnabledList || comboReady) {
      var cookieLang = readCookieLanguage();
      if (cookieLang) {
        currentLanguage = cookieLang;
      }
      buildLanguageOptions(combo);
      bindControls();
      protectTriggersFromTranslate();
      restoreWidgetEnglishCopy();
      if (window.ttLanguageSelector && window.ttLanguageSelector.refreshTriggers) {
        window.ttLanguageSelector.refreshTriggers();
      }
      if (cookieLang && cookieLang !== 'en') {
        updateComplexityUi();
        scheduleTranslateComplexity(cookieLang, currentComplexity, 2200);
      } else {
        updateComplexityUi();
      }
      // If Google combo is still loading, keep polling so translation apply works later.
      if (!comboReady) {
        (function pollCombo(tryCount) {
          if (tryCount >= 100) {
            return;
          }
          window.setTimeout(function () {
            var later = getTranslateCombo();
            if (later && later.options.length > 1) {
              buildLanguageOptions(later);
              return;
            }
            pollCombo(tryCount + 1);
          }, 100);
        })(attempts || 0);
      }
      return;
    }
    if ((attempts || 0) < 100) {
      setTimeout(function () {
        waitForCombo((attempts || 0) + 1);
      }, 100);
      return;
    }
    if (grid && !grid.children.length) {
      grid.innerHTML = '<p class="tt-lang-loading-fallback px-3 py-2 text-muted mb-0">Language list is still loading. Check your connection, then close and reopen this menu.</p>';
    }
    bindWidgetOptions();
  }

  bindWidgetShell();
  if (widget.dataset.ttLangComboWait !== '1') {
    widget.dataset.ttLangComboWait = '1';
    waitForCombo(0);
  }
}

document.addEventListener('DOMContentLoaded', function () {
  initCustomLanguageSelector();
});


// Initialize Google Translate



// nav search


   /**
 * TopTeen Search Functionality
 * This script handles the search functionality for the TopTeen website
 */

// Search functionality has been moved to search.js to avoid conflicts
// The new search.js handles all search functionality including AJAX calls

// nav search








