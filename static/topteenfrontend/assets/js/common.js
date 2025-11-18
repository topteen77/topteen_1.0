// CAROUSEL WITH 4 ELEMENTS
$(".carouselContainer").each(function (idx, el) {
  const noOfSlides = +el?.dataset?.slides || 4;
  const carousel = el.querySelector(".customCarousel");
  const sliderId = `slider-${idx + 1}`;
  if (!carousel) {
    return;
  }
  carousel.dataset.id = sliderId;
  const arrowsDiv = $(this).siblings(".navArrows")[0];
  const nextArrow = arrowsDiv.querySelector(".nextArrow");
  const prevArrow = arrowsDiv.querySelector(".prevArrow");
  nextArrow.id = `next-${idx + 1}`;
  prevArrow.id = `prev-${idx + 1}`;
  $(`*[data-id="${sliderId}"]`).slick({
    infinite: false,
    slidesToShow: noOfSlides,
    slidesToScroll: 1,
    arrows: true,
    nextArrow: $(`#next-${idx + 1}`),
    prevArrow: $(`#prev-${idx + 1}`),
    responsive: [
      {
        breakpoint: 1200,
        settings: {
          slidesToShow: noOfSlides,
          slidesToScroll: 1,
          arrows: true,
        },
      },
      {
        breakpoint: 480,
        settings: {
          slidesToShow: 2,
          slidesToScroll: 1,
          arrows: true,
        },
      },
      {
        breakpoint: 370,
        settings: {
          slidesToShow: 1,
          slidesToScroll: 1,
          arrows: true,
        },
      },
    ],
  });
});

// TABBED CAROUSEL
$(".tabContainer").each((_, container) => {
  if (!container) return;
  //CONTAINER OF TABS
  const tabList = container.querySelector(".tabList");
  // CONTAINER OF TAB PANELS
  const tabPanelsList = container.querySelector(".tabPanelsList");
  if (!tabPanelsList) return;
  const noOfSlides = +tabPanelsList.dataset?.slides || 4;
  // ALL TABS
  const tabs = container.querySelectorAll(".tab");
  //ALL PANELS
  const panels = container.querySelectorAll(".tabPanel");
  // CAROUSEL ID
  const carouselId = tabPanelsList.querySelector("[data-id]")?.dataset.id;
  let arrowId;
  if (carouselId) {
    arrowId = carouselId.split("-")[1];
  }
  tabList.addEventListener("click", (e) => {
    const target = e.target.closest(".tab");
    if (!target) {
      return;
    }
    // DESTROY CAROUSEL
    $(`[data-id="${carouselId}"]`).slick("unslick");
    const targetPanel = tabPanelsList.querySelector(target.dataset.tabsTarget);

    [...tabs].forEach((el) => {
      el.classList.remove("activeTab");
    });
    [...panels].forEach((el) => {
      el.removeAttribute("data-id");
      el.classList.add("hidden");
    });
    target.classList.add("activeTab");
    targetPanel.dataset.id = carouselId;
    targetPanel.classList.remove("hidden");

    $(`[data-id="${carouselId}"]`).slick({
      infinite: true,
      slidesToShow: noOfSlides,
      slidesToScroll: 1,
      arrows: true,
      nextArrow: $(`#next-${arrowId}`),
      prevArrow: $(`#prev-${arrowId}`),
      responsive: [
        {
          breakpoint: 480,
          settings: {
            slidesToShow: 2,
            slidesToScroll: 1,
            arrows: false,
          },
        },
        {
          breakpoint: 1200,
          settings: {
            slidesToShow: noOfSlides,
            slidesToScroll: 1,
            arrows: true,
          },
        },
      ],
    });
  });
});

// CONTROLLING SIDEBAR

const trigger = document.querySelector("#trigger");
const sidebar = document.querySelector("#sidebar");
const closeBtn = document.querySelector("#closeBtn");

trigger?.addEventListener("click", function () {
  if (!sidebar) {
    return;
  }
  sidebar.classList.remove("-translate-x-full");
});

closeBtn?.addEventListener("click", function () {
  if (!sidebar) {
    return;
  }
  sidebar.classList.add("-translate-x-full");
});

// HANDLING HEADER PANEL

const careerPanel = document.querySelector("#careerPanel");
const allTabs = document.querySelector(".allTabs");
const tabs = document.querySelectorAll(".tab") || [];
const tabArray = [...tabs];

const activateTab = function (activeClass, inactiveClass, applyStyle) {
  tabArray.forEach((el) => {
    const idx = el.dataset.idx;
    if (applyStyle) {
      const canReturn = applyStyle(idx);
      if (canReturn) return;
    }
    el.classList.remove(activeClass);
    if (inactiveClass) {
      el.classList.add(inactiveClass);
    }
  });
};

document.body.addEventListener("click", function (e) {
  const parent = e.target.closest("#headerPanel");
  if (!parent) {
    careerPanel?.classList.add("hidden");
    activateTab("activeBtn", "inactiveBtn", null);
  }
});

tabArray.forEach((el, idx) => {
  el.setAttribute("data-idx", `el-${idx}`);
});

allTabs?.addEventListener("click", function (e) {
  const target = e.target.closest(".tab");
  if (!target) return;
  const activeClass = allTabs.dataset.active;
  const inactiveClass = allTabs.dataset.inactive;
  const targetIdx = target.dataset.idx;

  const applyStyle = function (elIdx) {
    if (targetIdx === elIdx) {
      target.classList.add(activeClass);
      return true;
    }
  };

  activateTab(activeClass, inactiveClass, applyStyle);
  careerPanel?.classList.remove("hidden");
});

// // KNOW MORE CODE

const knowMoreBtn = document.querySelectorAll(".knowMore");
const btnList = knowMoreBtn ? [...knowMoreBtn] : [];

btnList.forEach((btn) => {
  const container = btn.closest(".parentContainer");
  if (!container) {
    return;
  }
  const paraTag = container.querySelector("p");
  const limit = +container?.dataset?.limit || 50;
  const originalStr = paraTag.textContent;
  const str = `${paraTag.textContent?.trim()?.slice(0, limit)}${
    paraTag.textContent?.length > limit ? "..." : ""
  }`;
  paraTag.textContent = str;

  btn.addEventListener("click", function (e) {
    if (e.target.textContent.trim().toLowerCase() === "know more") {
      paraTag.textContent = originalStr;
      e.target.textContent = "SHOW LESS";
    } else {
      paraTag.textContent = str;
      e.target.textContent = "KNOW MORE";
    }
  });
});

// Faq
const ftabs = document.querySelectorAll("[data-tab-target]");
const tabContents = document.querySelectorAll("[data-tab-content]");
ftabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    const target = document.querySelector(tab.dataset.tabTarget);
    // console.log("clicked");
    tabContents.forEach((tabContent) => {
      tabContent.classList.add("hidden");
    });
    ftabs.forEach((tab) => {
      tab.classList.remove("activeTab");
    });
    tab.classList.add("activeTab");
    target.classList.remove("hidden");
  });
});

// shortlist career
$(".shortlistcareer").each(function () {
  $(this).on("click", function () {
    var careerslug = $(this).data("careerslug");

    $.ajax({
      type: "POST",
      url: shrtlstcareer,
      data: { careerslug: careerslug },
      success: function (data) {
        fireAlert(data.message, "success");
        // var elid = $("#"+courseslug);
        //  console.log($(this).html());
        const buttontext = document.querySelectorAll(
          "button[data-careerslug='" + careerslug + "'] .buttontext"
        );
        [...buttontext].forEach((el) => {
          el.textContent = data.value;
        });
        // buttontext.textContent=data.value
        //  // $(`button[data-careerslug='${careerslug}']`).text(data.value);
      },
      error: function (xhr, ajaxOptions, thrownError) {
        if (xhr.status == 403) {
          if (confirm("You must be logged in, proceed?")) {
            window.location.href = loginurl;
          }
        }
        if (xhr.status == 400) {
          fireAlert("The Product Cannot Be Added at the moment.", "error");
        }
      },
      cache: false,
    });
  });
});

// shortlist career
$(".shortlistcollege").each(function () {
  $(this).on("click", function () {
    var collegeslug = $(this).data("collegeslug");

    $.ajax({
      type: "POST",
      url: shortlistcollege,
      data: { collegeslug: collegeslug },
      success: function (data) {
        fireAlert(data.message, "success");
        // var elid = $("#"+courseslug);
        //  console.log($(this).html());
        const buttontext = document.querySelectorAll(
          "button[data-collegeslug='" + collegeslug + "'] .buttontext"
        );
        [...buttontext].forEach((el) => {
          el.textContent = data.value;
        });
        // buttontext.textContent=data.value
        //  // $(`button[data-careerslug='${careerslug}']`).text(data.value);
      },
      error: function (xhr, ajaxOptions, thrownError) {
        if (xhr.status == 403) {
          if (confirm("You must be logged in, proceed?")) {
            window.location.href = loginurl;
          }
        }
        if (xhr.status == 400) {
          fireAlert("The Product Cannot Be Added at the moment.", "error");
        }
      },
      cache: false,
    });
  });
});


