$(function() {

    var WEB_SOCKET_SWF_LOCATION = '/static/js/socketio/WebSocketMain.swf';
    var ev_sock = io.connect('/event');

    ev_sock.on('connect',
         function () {
            ev_sock.emit('register', 'test registration msg');
        }
    )

    ev_sock.on('new_call',
        function (call_id, call_url) {
            var msg_html = '<p>User call #' + call_id + ':<a href="' + call_url + '" target="_blank">Click here to answer</a></p>';
            $('#lines').append(msg_html)
            alert('User call #' + call_id + ', please check your window to answer');
        }
    )
});
