// CAROUSEL WITH 4 ELEMENTS

$(".carouselContainer").each(function (idx, el) {
  const noOfSlides = +el?.dataset?.slides || 4;
  const carousel = el.querySelector(".customCarousel");
  const sliderId = `slider-${idx + 1}`;
  carousel.dataset.id = sliderId;
  const arrowsDiv = $(this).siblings(".navArrows")[0];
  const nextArrow = arrowsDiv.querySelector(".nextArrow");
  const prevArrow = arrowsDiv.querySelector(".prevArrow");
  nextArrow.id = `next-${idx + 1}`;
  prevArrow.id = `prev-${idx + 1}`;
  $(`*[data-id="${sliderId}"]`).slick({
    infinite: true,
    slidesToShow: noOfSlides,
    slidesToScroll: 1,
    arrows: true,
    nextArrow: $(`#next-${idx + 1}`),
    prevArrow: $(`#prev-${idx + 1}`),
    responsive: [
      {
        breakpoint: 360,
        settings: {
          slidesToShow: 1,
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

// TABBED CAROUSEL
$(".tabContainer").each((_, container) => {
  //CONTAINER OF TABS
  const tabList = container.querySelector(".tabList");
  // CONTAINER OF TAB PANELS
  const tabPanelsList = container.querySelector(".tabPanelsList");
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
const allTabs = document.querySelectorAll(".allTabs");
const tabs = document.querySelectorAll(".tab") || [];

// document.body.addEventListener("click", function (e) {
//   const parent = e.target.closest("#headerPanel");
//   const activeClass = "activeBtn";
//   if (e.target.closest("#headerPanel")) {
//     return;
//   }
//   careerPanel?.classList.add("hidden");
//   [...tabs].forEach((el) => {
//     el.classList.remove(activeClass);
//   });
// });

[...allTabs]?.forEach((allTabs) => {
  const tabs = allTabs?.querySelectorAll(".tab");
  allTabs?.addEventListener("click", function (e) {
    const target = e.target.closest(".tab");
    console.log(allTabs.dataset.active);
    if (!target) return;
    const activeClass = allTabs.dataset.active;
    [...tabs].forEach((el) => {
      el.classList.remove(activeClass);
    });
    careerPanel?.classList.remove("hidden");
    target.classList.add(activeClass);
  });
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
// /////////////////////////////////////

const parentDiv = document.querySelector(".explore_college");
const container = parentDiv?.querySelector(".carouselContainer");

$(".explore_college  carouselContainer").slick("unslick");
$(".explore_college").children(".carousel").slick("unslick");
