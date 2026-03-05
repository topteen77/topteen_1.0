// $(document).ready(function () {
//   $(".careerTracksCarousel").slick({
//     infinite: true,
//     slidesToShow: 4,
//     slidesToScroll: 1,
//     arrows: true,
//     nextArrow: $(".nextArr"),
//     prevArrow: $(".prevArr"),
//   });
// });

// $(document).ready(function () {
//   $(".coursesCarousel").slick({
//     infinite: true,
//     slidesToShow: 4,
//     slidesToScroll: 1,
//     arrows: true,
//     nextArrow: $(".nextCourse"),
//     prevArrow: $(".prevCourse"),
//   });
// });

// $(document).ready(function () {
//   $(".careersCarousel").slick({
//     infinite: true,
//     slidesToShow: 4,
//     slidesToScroll: 1,
//     arrows: true,
//     nextArrow: $(".nextCareer"),
//     prevArrow: $(".prevCareer"),
//   });
// });

// $(document).ready(function () {
//   $(".collegesCarousel").slick({
//     infinite: true,
//     slidesToShow: 4,
//     slidesToScroll: 1,
//     arrows: true,
//     nextArrow: $(".nextCollege"),
//     prevArrow: $(".prevCollege"),
//   });
// });

// $(".carouselContainer").each(function (idx, el) {
//   console.log(el, idx);
//   const carousel = el.querySelector(".customCarousel");
//   console.log(this);
//   const sliderId = `slider-${idx + 1}`;
//   carousel.dataset.id = sliderId;
//   console.log($(this).siblings(".navArrows")[0]);
//   const arrowsDiv = $(this).siblings(".navArrows")[0];
//   const nextArrow = arrowsDiv.querySelector(".nextArrow");
//   const prevArrow = arrowsDiv.querySelector(".prevArrow");
//   nextArrow.id = `next-${idx + 1}`;
//   prevArrow.id = `prev-${idx + 1}`;
//   $(`*[data-id="${sliderId}"]`).slick({
//     infinite: true,
//     slidesToShow: 4,
//     slidesToScroll: 1,
//     arrows: true,
//     nextArrow: $(`#next-${idx + 1}`),
//     prevArrow: $(`#prev-${idx + 1}`),
//   });
// });

$(document).ready(function () {
  $(".testimonialCarousel").slick({
    infinite: true,
    slidesToShow: 1,
    slidesToScroll: 1,
    arrows: true,
    nextArrow: $(".nextTest"),
    prevArrow: $(".prevTest"),
    centerMode: true,
  });
});

// const DUMMY_DATA = [
//   {
//     img: "../assets/images/test_Img.png",
//     name: "Darel Steward",
//     desg: "Parent",
//     info: "The arts seminar conducted by Dr. Shevchenko helped me understand artistic approaches to human expression. The arts seminar conducted by Dr. Shevchenko helped me understand artistic approaches to human expression and innovation.",
//   },
//   {
//     img: "../assets/images/test_Img.png",
//     name: "John Steward",
//     desg: "chief",
//     info: "second data seminar conducted by Dr. Shevchenko helped me understand artistic approaches to human expression. The arts seminar conducted by Dr. Shevchenko helped me understand artistic approaches to human expression and innovation.",
//   },
//   {
//     img: "../assets/images/test_Img.png",
//     name: "Jack Steward",
//     desg: "vice-chairman",
//     info: "Third data conducted by Dr. Shevchenko helped me understand artistic approaches to human expression. The arts seminar conducted by Dr. Shevchenko helped me understand artistic approaches to human expression and innovation.",
//   },
//   {
//     img: "../assets/images/test_Img.png",
//     name: "Lisa Steward",
//     desg: "chairman",
//     info: "Fourth data conducted by Dr. Shevchenko helped me understand artistic approaches to human expression. The arts seminar conducted by Dr. Shevchenko helped me understand artistic approaches to human expression and innovation.",
//   },
// ];

const testimonial = document.querySelector(".mobileTest");
// const heading = testimonial.querySelector(".heading");
// const desg = testimonial.querySelector(".desg");
// const content = testimonial.querySelector(".content");
const images = document.querySelectorAll(".imgDiv");
const imgArray = [...images];
const imageBlock = document.querySelector(".images");
if (imageBlock) {
  imageBlock.addEventListener("click", (e) => {
    e.preventDefault();
    const target = e.target;
    if (!target.classList.contains("image")) {
      return;
    }

    const parent = target.closest(".imgDiv");
    imgArray.forEach((img) => {
      // console.log(img);
      img.classList.add("opacity-[0.4]");
    });
    parent.classList.remove("opacity-[0.4]");
    // const idx = parent.dataset.idx;
    // const data = DUMMY_DATA[idx];
    // heading.textContent = data.name;
    // desg.textContent = data.desg;
    // content.textContent = data.info;
    // console.log(parent.dataset.idx);
  });
}

// const tabList = document.querySelector(".tablist");
// const allTabs = document.querySelectorAll(".tab");
// const tabPanels = document.querySelectorAll(".tabpanel");
// const collegeTabList = document.querySelector(".collegeTabList");
// const collegeTabs = document.querySelectorAll(".collegeTab");
// const collegeTabPanels = document.querySelectorAll(".collegeTabPanel");

// tabList.addEventListener("click", (e) => {
//   const target = e.target.closest(".tab");
//   if (!target) {
//     return;
//   }
//   $(".careersCarousel").slick("unslick");
//   const tabPanel = document.querySelector(target.dataset.tabsTarget);

//   [...allTabs].forEach((el) => {
//     el.classList.remove("activeTab");
//   });
//   [...tabPanels].forEach((el) => {
//     el.classList.remove("careersCarousel");
//     el.classList.add("hidden");
//   });

//   target.classList.add("activeTab");
//   tabPanel.classList.add("careersCarousel");
//   tabPanel.classList.remove("hidden");

//   $(".careersCarousel").slick({
//     infinite: true,
//     slidesToShow: 4,
//     slidesToScroll: 1,
//     arrows: true,
//     nextArrow: $(".nextCareer"),
//     prevArrow: $(".prevCareer"),
//   });
// });

// tabList.addEventListener("click", (e) => {
//   const target = e.target;
//   console.log(target);
//   makeCarouselTabbed(
//     target,
//     "careersCarousel",
//     [],
//     allTabs,
//     tabPanels,
//     "nextCareer",
//     "prevCareer",
//     "tab"
//   );
// });

// collegeTabList.addEventListener("click", (e) => {
//   const target = e.target;
//   console.log(target);
//   makeCarouselTabbed(
//     target,
//     "collegesCarousel",
//     [],
//     collegeTabs,
//     collegeTabPanels,
//     "nextCollege",
//     "prevCollege",
//     "collegeTab"
//   );
// });

// const makeCarouselTabbed = function (
//   targetNew,
//   carouselClass,
//   tablist,
//   allTabs,
//   allTabPanels,
//   nextArrow,
//   prevArrow,
//   tabClass
// ) {
//   const target = targetNew.closest(`.${tabClass}`);
//   console.log(target);
//   if (!target) {
//     return;
//   }
//   $(`.${carouselClass}`).slick("unslick");
//   const tabPanel = document.querySelector(target.dataset.tabsTarget);

//   [...allTabs].forEach((el) => {
//     el.classList.remove("activeTab");
//   });
//   [...allTabPanels].forEach((el) => {
//     el.classList.remove(carouselClass);
//     el.classList.add("hidden");
//   });

//   target.classList.add("activeTab");

//   tabPanel.classList.add(carouselClass);
//   tabPanel.classList.remove("hidden");

//   $(`.${carouselClass}`).slick({
//     infinite: true,
//     slidesToShow: 4,
//     slidesToScroll: 1,
//     arrows: true,
//     nextArrow: $(`.${nextArrow}`),
//     prevArrow: $(`.${prevArrow}`),
//   });
// };

// TABS CONTAINER WITH SLICK
// $(".tabContainer").each((_, container) => {
//   //CONTAINER OF TABS
//   const tabList = container.querySelector(".tabList");
//   // CONTAINER OF TAB PANELS
//   const tabPanelsList = container.querySelector(".tabPanelsList");
//   // ALL TABS
//   const tabs = container.querySelectorAll(".tab");
//   //ALL PANELS
//   const panels = container.querySelectorAll(".tabPanel");
//   // CAROUSEL ID
//   const carouselId = tabPanelsList.querySelector("[data-id]")?.dataset.id;
//   tabList.addEventListener("click", (e) => {
//     const target = e.target.closest(".tab");
//     console.log(target);
//     if (!target) {
//       return;
//     }
//     // DESTROY CAROUSEL
//     $(`[data-id="${carouselId}"]`).slick("unslick");
//     const targetPanel = tabPanelsList.querySelector(target.dataset.tabsTarget);

//     console.log(carouselId);

//     [...tabs].forEach((el) => {
//       el.classList.remove("activeTab");
//     });
//     [...panels].forEach((el) => {
//       console.log(el);
//       el.removeAttribute("data-id");
//       el.classList.add("hidden");
//     });
//     target.classList.add("activeTab");
//     targetPanel.dataset.id = carouselId;
//     targetPanel.classList.remove("hidden");

//     $(`[data-id="${carouselId}"]`).slick({
//       infinite: true,
//       slidesToShow: 4,
//       slidesToScroll: 1,
//       arrows: true,
//       // nextArrow: $(`.${nextArrow}`),
//       // prevArrow: $(`.${prevArrow}`),
//     });
//   });
// });

const triggerPopup = document.querySelectorAll(".triggerPopup");
let popUpDiv = document.querySelector(".popUpDiv");
let yTembed = document.querySelector(".yTembed");
let yTurl = yTembed?.getAttribute("src");

const openPopUp = () => {
  popUpDiv.style.display = "block";
  yTembed?.setAttribute("src", yTurl);
};

let popUpDivEV = document.querySelector(".popUpDivEV");
let yTembedEV = document.querySelector(".yTembedEV");

const openPopUpEV = (dynamicYTurl) => {
  yTembedEV.setAttribute("src", dynamicYTurl);
  popUpDivEV.style.display = "block";
};

const closePopUp = () => {
  popUpDiv.style.display = "none";
  // Clear iframe src to stop video playback when popup is closed
  yTembed?.setAttribute("src", "about:blank");
};

const closePopUpEV = () => {
  popUpDivEV.style.display = "none";
  // Clear iframe src to stop video playback when popup is closed
  yTembedEV.setAttribute("src", "about:blank");
};

const careerpopuparray = document.querySelectorAll(".careerpopup");
[...careerpopuparray]?.forEach((elem) => {
  elem.addEventListener("click", function (e) {
    const target = e.target.closest(".careerpopup");
    const url = target.dataset.url;
    openPopUpEV(url);
  });
});

const pagebutton = document.querySelectorAll(".pagebtn");
pagebutton.forEach((btn) => {
  btn.addEventListener("click", () => {
    pagebutton.forEach((btn) => {
      btn.classList.remove("active");
    });
    btn.classList.add("active");
  });
});

document.getElementById("childfaq")?.addEventListener("click", () => {
  console.log("Hello Parent");
  document.getElementById("sfaq").classList.add("activeTab");
  document.getElementById("achildFAQ").classList.remove("hidden");
  document.getElementById("pfaq").classList.remove("activeTab");
  document.getElementById("aparentFAQ").classList.add("hidden");
});

// let popUpCd = document.querySelector(".popUpDivCD");
// let closingBtn = document.querySelector(".closingBtn");
// let triggerCD = document.querySelector(".triggerCDPopUp")

// triggerCD.addEventListener("click", function(){
//   console.log("hello");
//   popUpCd.style.display = "block";
// })

// triggerCD.addEventListener("click", (e) => {
//   e.preventDefault();
//   console.log(e.target);
//   popUpCd.style.display = "block";
//   console.log("i am working")
// })

// console.log("outside", triggerCD);

// closingBtn.addEventListener("click", function(){
//   popUpCd.style.display = "none";
// })

// const popTabs = document.querySelectorAll("[data-tab-target]");
// const popContent = document.querySelectorAll("[data-tab-content]");

// popTabs.forEach(tab => {
//   tab.addEventListener("click", function(e){
//     console.log(e.target);
//     const target = document.querySelector(tab.dataset.tabTarget);
//     console.log(target)

//     popContent.forEach(popContent => {
//       popContent.classList.add("hidden");
//     })

//     popTabs.forEach(tab => {
//       tab.classList.remove("activeTab");
//     })

//     tab.classList.add("activeTab");
//     target.classList.remove("hidden");

//     let btn = target.querySelector(".closingBtn");
//     btn.addEventListener("click", function(){
//     target.classList.add("hidden");
//     })

//   })
// })
