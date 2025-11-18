const storyPopUp = document.querySelector(".storyPop");
const slideParent = document.querySelector(".slideParent")
const storySlide = document.querySelector(".storySlides")
const slideImgParent = document.querySelector(".slideImgParent")
// Story Opening Function

function storyFunc(evt, storyName){

  const storyContent = document.querySelectorAll(".storyContent");
  const storyTarget = document.querySelectorAll(`.${storyName}`);

  storyPopUp.style.display = "block"

  storyContent.forEach(elem => {
    elem.classList.add("hidden");
  })

  const selectedSlideImgs = slideImgParent.querySelectorAll(`.${storyName}`)

  console.log(slideImgParent)
  console.log(selectedSlideImgs);

  selectedSlideImgs.forEach(elem => {
    storySlide.appendChild(elem)
  })

  storyTarget.forEach(elem => {
    elem.classList.remove("hidden");
  })

  evt.currentTarget.classList.add("active");
  console.log(storySlide);
  
  $(storySlide).slick({
    dots: true,
    infinite: false,
    speed: 300,
    arrows: true,
    autoplay: false,
    nextArrow: $(".storyNextBtn"),
    prevArrow: $(".storyPrevBtn"),
    slidesToShow: 1,
    slidesToScroll: 1,
    responsive: [
      {
        breakpoint: 1024,
        settings: {
          slidesToShow: 1,
          slidesToScroll: 1,
          infinite: true,
          dots: true
        }
      },
      {
        breakpoint: 600,
        settings: {
          slidesToShow: 1,
          slidesToScroll: 1
        }
      },
      {
        breakpoint: 480,
        settings: {
          slidesToShow: 1,
          slidesToScroll: 1
        }
      }
    ]
  });
}


// Story Closing Function
const storyClose = document.querySelectorAll(".storyCloseBtn");

storyClose.forEach(elem => {
  elem.addEventListener("click", function(){
    storyPopUp.style.display = "none";
    const storyChild = storySlide.querySelectorAll(".storyContent");
    
    // Unslick
    $(storySlide).slick('unslick');

    // Bringing the images back from slick 
    storyChild.forEach(elem => {
      slideImgParent.appendChild(elem)
    })
  
  })
})


