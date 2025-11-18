$(document).ready(function () {
    $(".newPages").slick({
        dots: true,
        speed: 300,
        slidesToShow: 1,
        centerMode: true,
        variableWidth: true,
        adaptiveHeight: true,
        
        // adaptiveWidth: true,
        responsive: [
            {
                breakpoint: 375,
                settings: {
                    dots: true,
                    speed: 300,
                    slidesToShow: 1,
                    adaptiveHeight: true,
                    centerMode: true,
                    variableWidth: true,
                    adaptiveHeight: true,

                }
            },
        ]
    });


    
     var indexVal=0;
     $(".slideOnButton").click(function(e){
         e.preventDefault();
        // slideIndex = $(this).index();
         $( '.newPages' ).slick('slickGoTo', indexVal);
        indexVal=indexVal+1;
    
      });
    //End of sliding function for a button 
    
    //Sliding function for back arrow  
    var indexValue = 4
    $(".slideOnArrow").click(function(e){
    e.preventDefault();
   // slideIndex = $(this).index();
    $( '.newPages' ).slick('slickGoTo', indexValue);
    indexValue=indexValue-1;

 });
//End of sliding function for back arrow
    
});

//MotivePages
$(".streamTab").click(function(){
    $(this).toggleClass("activeTab");
    $(".planCareerTab").removeClass("activeTab");
    $(".optionsTab").removeClass("activeTab");
})
$(".planCareerTab").click(function(){
    $(this).toggleClass("activeTab");
    $(".streamTab").removeClass("activeTab");
    $(".optionsTab").removeClass("activeTab");
})
$(".optionsTab").click(function(){
    $(this).toggleClass("activeTab");
    $(".planCareerTab").removeClass("activeTab");
    $(".streamTab").removeClass("activeTab");
})
//End of Motive Pages

//Hobbies
$(".hobbiesTab").click(function(){
    $(this).toggleClass("activeTab");
})
//End of Hobbies

$(".subDiv").click(function(){
    $(this).toggleClass("selectedDiv activeTab");
})


