const introSection = document.querySelector(".introSection");
const stickyHeaderForMobile = document.querySelector(".stickyHeader");

const options = {
  root: null,
  threshold: 0,
};

const callback = function (entries) {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      stickyHeaderForMobile?.classList.add("hidden");
    } else {
      stickyHeaderForMobile?.classList.remove("hidden");
    }
  });
};

const Observer = new IntersectionObserver(callback, options);
if (introSection) Observer.observe(introSection);

// KNOW MORE CODE
function toggleText() {
  var moreText = document.getElementById("more");
  var button = document.getElementById("button");

  if (moreText.classList.contains("hidden")) {
    moreText.classList.remove("hidden");
    button.innerHTML = "SHOW LESS";
  } else {
    moreText.classList.add("hidden");
    button.innerHTML = "KNOW MORE";
  }
}

$(document).ready(function () {
  // $(".leadingProfessionsCarousel").slick({
  //   infinite: true,
  //   slidesToShow: 3,
  //   slidesToScroll: 1,
  //   arrows: true,
  //   nextArrow: $(".lpsNextBtn"),
  //   prevArrow: $(".lpsPrevBtn"),
  //   draggable: false,
  //   responsive: [
  //     {
  //       breakpoint: 768,
  //       settings: {
  //         arrows: true,
  //         slidesToShow: 2,
  //         slidesToScroll: 1,
  //         centerPadding: "40px",
  //       },
  //     },
  //     {
  //       breakpoint: 480,
  //       settings: {
  //         arrows: true,
  //         slidesToShow: 1,
  //         slidesToScroll: 1,
  //       },
  //     },
  //   ],
  // });

  const createOptions = function (carouselId) {
    return {
      infinite: true,
      slidesToShow: 3,
      slidesToScroll: 1,
      arrows: true,
      nextArrow: $(`#${carouselId} .next`),
      prevArrow: $(`#${carouselId} .prev`),
      draggable: false,
      responsive: [
        {
          breakpoint: 768,
          settings: {
            arrows: false,
            slidesToShow: 2,
            slidesToScroll: 1,
            // centerPadding: "40px",
          },
        },
        {
          breakpoint: 480,
          settings: {
            arrows: false,
            slidesToShow: 2,
            slidesToScroll: 1,
          },
        },
        {
          breakpoint: 365,
          settings: {
            arrows: false,
            slidesToShow: 1,
            slidesToScroll: 1,
          },
        },
      ],
    };
  };
  const carouselContainers = document.querySelectorAll(".carouselContainer");

  [...carouselContainers]?.forEach((el, idx) => {
    // const carousel = el.querySelector(".carousel");
    const randomId = `carousel-${idx}`;
    el.id = randomId;
    const options = createOptions(randomId);
    $(`#${randomId} .carousel`).slick(options);
  });
});

const popTabs = document.querySelectorAll("[data-tab-target]");
const popContent = document.querySelectorAll("[data-tab-content]");

popTabs.forEach((tab) => {
  tab.addEventListener("click", function (e) {
    console.log(e.target);
    const target = document.querySelector(tab.dataset.tabTarget);
    console.log(target);

    popContent.forEach((popContent) => {
      popContent.classList.add("hidden");
    });

    popTabs.forEach((tab) => {
      tab.classList.remove("activeTab");
    });

    tab.classList.add("activeTab");
    target.classList.remove("hidden");

    let btn = target.querySelector(".closingBtn");
    btn.addEventListener("click", function () {
      target.classList.add("hidden");
    });
  });
});

// Search Bar function

const headingSec = document.querySelectorAll(".headingSection");

headingSec.forEach((elem) => {
  const firstHeader = elem.querySelector(".firstHeader");
  const searchHeader = elem.querySelector(".searchBarHeader");

  const searchTrigger = elem.querySelector(".searchBarTrigger");
  const searchClose = elem.querySelector(".searchBarCloseBtn");

  searchTrigger.addEventListener("click", function () {
    firstHeader.classList.add("hidden");
    searchHeader.classList.remove("hidden");
  });

  searchClose.addEventListener("click", function () {
    searchHeader.classList.add("hidden");
    firstHeader.classList.remove("hidden");
  });
});

// Text truncate function
function truncateStr(str, num) {
  if (str.length > num) {
    return str.slice(0, num) + "...";
  } else {
    return str;
  }
}

const profSummaryDesktop = document.querySelectorAll(".profSummaryDesktop");

profSummaryDesktop.forEach((elem) => {
  const summaryText = elem.textContent;
  const updatedText = truncateStr(summaryText, 20);
  elem.textContent = updatedText;
});

const profSummaryMobile = document.querySelectorAll(".profSummaryMobile");

profSummaryMobile.forEach((elem) => {
  const summaryText = elem.textContent;
  const updatedText = truncateStr(summaryText, 24);
  elem.textContent = updatedText;
});


// Rating 
let stars= document.querySelectorAll(".stars i");
let finalRating=0;

stars.forEach((elem, ind1) => {
  elem.addEventListener('click', function(){
    stars.forEach((elem, ind2) => {
      ind1 >= ind2 ? elem.classList.add('checkedStar') : elem.classList.remove('checkedStar')
    })
  })
} )

const ratingSubmitFunc = function(param,param2){
  let checkedStars = document.querySelectorAll('.checkedStar');
  $.ajax({
    url: param,
    data: {'rate':checkedStars.length,'slug':param2},
    type: 'GET'
  }).done(function(response){
    // $('#ratingmsg').css({"display":"block"});
    console.log(response);
  });
  console.log(checkedStars.length);
  return checkedStars.length;
}

const ratingSubmitBtn = document.querySelector(".ratingSubmitBtn");
// ratingSubmitBtn.addEventListener('click', ratingSubmitFunc)


// JS for videos

const videos = document.querySelectorAll(".video");

videos.forEach(elem => {
  elem.addEventListener('play', function(){
    videos.forEach(item=> {
      if(item !== elem){
        item.pause();
      }
    })
  })
})

// videos.forEach(elem => {
//   elem.addEventListener('play', function(){
//     videos.forEach(item => {
//       item.pause();
//     })
//     elem.play()
//   })
// })




