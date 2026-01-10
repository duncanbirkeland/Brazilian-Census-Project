$(document).ready(function(){
   url = $("#geteventid").val();
   $("body").css({
    "background-image": "url('" + url + "')",
    "background-size": "cover"
   })
});