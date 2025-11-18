// $(".country_btn").each(function(e){
//     var $this = $(this);
    
//     $this.on("click", function(){
//       var country = $(this).attr('data-country');
//       console.log(country);
//       var parameter = "?country_name="+country;
//       explore_colleges(parameter);

//     })
   
//   });

//   function explore_colleges(parameter){
//     $.ajax({
//       url: window.location.href+parameter,
//       type: 'GET',
//       success: function (html) {
//        console.log("abc");
//         $('.explore_colleges').html(html);
          
//       }
//   });
//   }
