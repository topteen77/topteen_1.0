let beforeType = document.querySelector(".beforeType");
let afterType = document.querySelector(".afterType");
let nothingFound = document.querySelector(".nothingFound");
let mainPart = document.querySelector(".mainPart");
let searchBox = document.querySelector(".searchBox")

const focusFunc = () => {
    beforeType.classList.remove("hidden");
}

const inputFunc = () => {
    beforeType?.classList.add("hidden");
    // afterType.classList.remove("hidden");  
}

document.onclick = function(e){
  // If clicking on a link in search results, let it navigate naturally
  const clickedLink = e.target.closest('#desktopviewsearch a, #mobileviewsearch a, #searchresults a');
  if (clickedLink) {
    // Allow the link to navigate - don't interfere
    return;
  }
  
  // Don't close dropdown if clicking inside the search results container
  if (e.target.closest('#searchresults') || e.target.closest('#desktopviewsearch') || e.target.closest('#mobileviewsearch')) {
    return;
  }
  
  const parent = e.target.closest(".beforeType")
  
  if( !parent && !e.target.classList.contains("searchBox")){
      beforeType?.classList.add("hidden");
  }
}

// document.addEventListener('click', function(e){
//     const parent = e.target.closest(".beforeType")
//     console.log(parent)
//     if( !parent && !e.target.classList.contains("searchBox")){
//         beforeType.classList.add("hidden");
//     }
    
// }
// )



// searchBox.addEventListener("focusout", function(){
//     beforeType.classList.add("hidden");
    
// })

// first searchbar homepage

function SearchCollegeListHtml(parameter,is_mobile=false){
    
    $.ajax({
      url: clgajxsrchlst+parameter,
      type: 'GET',
      success: function (html) {
        if(is_mobile){
            $('#mobilesearchresults').html(html);
            document.getElementById("desktopviewsearch").classList.add("hidden");
            document.getElementById("mobileviewsearch").classList.remove("hidden");
        }
        else{
           $('#searchresults').html(html);
        }
      }
  });
  }
  
  function debounce(func, timeout = 1000){
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => { func.apply(this, args); }, timeout);
    };
  }
  function saveInput(){
    var slug = $(".triggerCountryList").data('countryslug');
    if(is_mobile){
        var mobileinpt=document.getElementById("mobilesaerch");
        if(mobileinpt.value.length >= 3){
        q="?search="+mobileinpt.value;
        SearchCollegeListHtml(q,is_mobile);
        }
  
        if (mobileinpt.value.length < 1){
      $(".givendiv").each(function(index,lstt){
        lstt.classList.add("hidden")
      });
            
        }
    }
    else{
        var desktopinpt=document.getElementById("collegesearch");
  
        if(desktopinpt.value.length >= 3){
        q="?search="+desktopinpt.value;
        console.log(q)
        SearchCollegeListHtml(q);
        }
        if (desktopinpt.value.length < 1){
      $(".givenlist").each(function(index,lstt){
        lstt.classList.add("hidden")
      });
        }
    }
  }
  const processChange = debounce(() => saveInput());
  
  var is_mobile = false;
  
  function mobileSearch(ismobile){
    const processChange = debounce(() => saveInput());
    is_mobile=ismobile;
    processChange()
  }

const searchinput=document.querySelector('.searchinput')
if (searchinput) {
  searchinput.addEventListener('keyup',function(e){
    const value = e.target.value;
    console.log(value)
    if (value.length>0){
        beforeType?.classList.add('hidden')
    }
    else if(value.length===0){
        beforeType?.classList.remove('hidden')
    }

    mobileSearch(false)


  })
}