// $('.storySlides').slick({
//     dots: true,
//     infinite: false,
//     speed: 300,
//     arrows: true,
//     autoplay: false,
//     nextArrow: $(".storyNextBtn"),
//     prevArrow: $(".storyPrevBtn"),
//     slidesToShow: 1,
//     slidesToScroll: 1,
//     responsive: [
//       {
//         breakpoint: 1024,
//         settings: {
//           slidesToShow: 1,
//           slidesToScroll: 1,
//           infinite: true,
//           dots: true
//         }
//       },
//       {
//         breakpoint: 600,
//         settings: {
//           slidesToShow: 1,
//           slidesToScroll: 1
//         }
//       },
//       {
//         breakpoint: 480,
//         settings: {
//           slidesToShow: 1,
//           slidesToScroll: 1
//         }
//       }

// });

const storyCarousels = document.querySelectorAll(".storyPopContent");

storyCarousels.forEach(elem => {

console.log(elem)
  const sliderClass = elem.querySelector(".storySlides")
  console.log(sliderClass)
  
    const prevArrowBtn = elem.querySelector(".storyPrevBtn");
    const nextArrowBtn = elem.querySelector(".storyNextBtn");
    
  
    $(sliderClass).slick({
      infinite: true,
      slidesToShow: 1,
      slidesToScroll: 1,
      arrows: true,
      nextArrow: nextArrowBtn,
      prevArrow: prevArrowBtn,
      dots: true,
      responsive: [
        {
          breakpoint: 480,
          settings: {
            slidesToShow: 1,
            slidesToScroll: 1,
            arrows: false,
            dots: true,
            infinite: true,
            // dotsClass: "listingDots",
            // appendDots: $(".listingDots"),
          },
        },
        {
          breakpoint: 1200,
          settings: {
            slidesToShow: 1,
            slidesToScroll: 1,
            arrows: true,
            dots: true,
            infinite: true,
  
            // dotsClass: "slickDots",
          },
        },
      ],
    });
  });