
$(document).ready(function () {
    if(window.location.pathname !== '/templates/events') {
        //SEt the overflow on all pages initially to be hidden
        $('body').css('overflow', 'hidden');
    }
    var previous = ''
    $(document).on('mouseenter', '#creditheader', function(){
        previous = $(this).html();
        // When hovering replace the text with a link to get more credits
        $(this).html('<a href="/requestcredits">Request Credits</a>');
    });

    $(document).on('mouseleave', '#creditheader', function(){
        // On mouseout, revert the content to the initial state
        $(this).html(previous);
    });
    var links = $('.loginhrefs')
    //Get the registration/login links

    if ($("#getloggedin").val()){
        links.hide()
        //Hide these links if the user is already logged in
    }

    var superuser = $('#getvariable').val();
    if (superuser == 'True'){
        $('#blockleft').append("<a href = '/templates/dashboard'> modify events </a>")
        //If the user is a superuser allow them to see the link to modify events
    }
  });