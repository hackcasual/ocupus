var hangingGet = null;
var request = null;
var localName;
var server;
var my_id = -1;
var other_peers = {};
var message_counter = 0;

var sdpConstraints = {'mandatory': {
                        'OfferToReceiveAudio':true, 
                        'OfferToReceiveVideo':true }};

var orchestrator = -1;

function handleServerNotification(data) {
  var parsed = data.split(',');
  if (parseInt(parsed[2]) != 0) {
    other_peers[parseInt(parsed[1])] = parsed[0];
    if (parsed[0] == "ocupus_orchestrator")
      orchestrator = parseInt(parsed[1])
  }
}

var localConnections = {};

var haveOffer = false;
var didIt = false;

var remoteConn;
var lastPeerId;

function setBitRate(sdp, videoBitRate)
 {
  sdp = sdp.replace( /b=AS([^\r\n]+\r\n)/g , '');
  // Set audio bandwidth low until we can get rid of it totally
  sdp = sdp.replace( /a=mid:audio\r\n/g , 'a=mid:audio\r\nb=AS:10\r\n');
  // 256 kilobits per second
  sdp = sdp.replace( /a=mid:video\r\n/g , 'a=mid:video\r\nb=AS:' + videoBitRate + '\r\n');
  return sdp;
 }

var hasShownReject = false;

function isGoodCandidate(conn) {
  if (window.location.hostname.search("172.17") != -1) {
    if (hasShownReject == false) {
      logLine("Running in VPN mode, rejecting all non VPN candidates"); 
      hasShownReject = true;
    }
    return conn.search("172.17") != -1;
  }
  if (hasShownReject == false) {
    logLine("*********** WARNING :: Not restricting candidates to VPN. If this is an official match, you're in trouble!"); 
    hasShownReject = true;
  }  
  return true;
}

// From http://stackoverflow.com/questions/4197591/parsing-url-hash-fragment-identifier-with-javascript
function getHashParams() {

    var hashParams = {};
    var e,
        a = /\+/g,  // Regex for replacing addition symbol with a space
        r = /([^&;=]+)=?([^&;]*)/g,
        d = function (s) { return decodeURIComponent(s.replace(a, " ")); },
        q = window.location.hash.substring(1);

    while (e = r.exec(q))
       hashParams[d(e[1])] = d(e[2]);

    return hashParams;
}

var streams = {};

var nettraff = {rx: -1, tx: -1, time: -1}
var rx_delta_mbps = 0;
var tx_delta_mbps = 0;

function handleOcupusMessage(message) {
  if (message.type === "log") {
    logLine(message.log);
  } else if (message.type === "nettraff") {
    if (nettraff.rx > 0) {
      rx_delta = message.rx - nettraff.rx;
      tx_delta = message.tx - nettraff.tx;
      time_delta = (window.performance.now() - nettraff.time) / 1000.0;

      tx_delta_mbps = (((tx_delta + rx_delta) * 8)/1e6) / time_delta;

    }
    nettraff.rx = message.rx;
    nettraff.tx = message.tx;
    nettraff.time = window.performance.now();    
  }
}

function handlePeerMessage(peer_id, data) {
  if (other_peers[peer_id] == "ocupus_orchestrator") {
    handleOcupusMessage(JSON.parse(data));
  }
  lastPeerId = peer_id;
  ++message_counter;

    if (data.search("offer") != -1) {
      var offerInfo = JSON.parse(data);
      var servers = null;
      haveOffer = true;

      var localPeerConnection = new RTCPeerConnection(servers);

      localPeerConnection.setRemoteDescription(new RTCSessionDescription(offerInfo));

      localPeerConnection.createAnswer(function (description) {
        localPeerConnection.setLocalDescription(description);
        description.sdp = setBitRate(description.sdp, 1024);
        sendToPeer(peer_id, JSON.stringify(description));
      }, null, sdpConstraints);
      localPeerConnection.onicecandidate = function (icb) {

        if (icb.candidate && isGoodCandidate(JSON.stringify(icb.candidate))) {
          setTimeout(50,sendToPeer(peer_id, JSON.stringify(icb.candidate)));
        }
};

      localPeerConnection.onaddstream = function gotRemoteStream(e){
        var vidid = "vid" + peer_id;

        $("#camera-panel").append("<div class='panel panel-primary'><div class='panel-heading'>" 
          + other_peers[peer_id] + "</div><video id='" + vidid + "' autoplay></video></div>");
        attachMediaStream($("#" + vidid).get(0), e.stream);
        streams[vidid] = e.stream;
      };

      localConnections[peer_id] = localPeerConnection;

    }  

    if (data.search("candidate") != -1 && isGoodCandidate(data)) {
      var candidateInfo = JSON.parse($.trim(data));
      candidateInfo.candidate = $.trim(candidateInfo.candidate);
      console.log(candidateInfo);
      var cand = new RTCIceCandidate(candidateInfo);

      cand.candidate = $.trim(cand.candidate);

      try {


      localConnections[peer_id].addIceCandidate(new RTCIceCandidate(candidateInfo));
      } catch (exc) {
        console.error(exc);
        console.log(new RTCIceCandidate(candidateInfo));
      }
      didIt = true;
    } 
}

function GetIntHeader(r, name) {
  var val = r.getResponseHeader(name);
  return val != null && val.length ? parseInt(val) : -1;
}

function showConnected() {
  logLine("Now connected to " + server);
  $("li.connection-status").html('<div class="connection-text">Connected</div><div class="fa fa-link fa-2x" style="color: white;">');
}

function showDisconnected() {
  logLine("Now disconnected from " + server);
  $("li.connection-status").html('<div class="connection-text">No Connection</div><div class="fa fa-unlink fa-2x" style="color: white;">');
}


function showError(status) {
          $("#alerts").append('<div class="alert alert-danger" data-dismiss="alert">' + status + '</div>');
          logLine("<span style='color:red'>" + status + "</span>");
}

function hangingGetCallback() {

    if (hangingGet.readyState != 4)
      return;
    if (hangingGet.status != 200) {
      console.log(hangingGet)
      showError("Lost connection to server" + hangingGet.statusText);
      my_id = -1;
      showDisconnected();
      disconnect();
    } else {
      var peer_id = GetIntHeader(hangingGet, "Pragma");
      if (peer_id == my_id) {
        handleServerNotification(hangingGet.responseText);
      } else {
        handlePeerMessage(peer_id, hangingGet.responseText);
      }
    }

    if (hangingGet) {
      hangingGet.abort();
      hangingGet = null;
    }

    if (my_id != -1)
      window.setTimeout(startHangingGet, 0);
}

function systemShutdown() {
  var confirm=prompt("Powering off ocupus. Only do this at the end of a match. Type poweroff to confirm ","");

  if (confirm=="poweroff")
  {
    sendToPeer(orchestrator, '{"topic":"system","message":"shutdown"}');
    logLine("Sending power off to ocupus");
  } else {
    logLine("Canceling power off");
  }
}

function systemReboot() {
  var confirm=prompt("Rebooting ocupus. Only do this if you're having trouble. Type reboot to confirm ","");

  if (confirm=="reboot")
  {
    sendToPeer(orchestrator, '{"topic":"system","message":"restart"}');
    logLine("Sending reboot to ocupus");
  } else {
    logLine("Canceling reboot");
  }
}

function startHangingGet() {
  try {
    hangingGet = new XMLHttpRequest();
    hangingGet.onreadystatechange = hangingGetCallback;
    hangingGet.ontimeout = onHangingGetTimeout;
    hangingGet.open("GET", server + "/wait?peer_id=" + my_id, true);
    hangingGet.send();  
  } catch (e) {
    showError(e.description);
    my_id = -1;
    showDisconnected();
  }
}

function onHangingGetTimeout() {
  showError("hanging get timeout. issuing again.");
  hangingGet.abort();
  hangingGet = null;
  if (my_id != -1)
    window.setTimeout(startHangingGet, 0);
}

function signInCallback() {


  try {
    if (request.readyState == 4) {
      if (request.status == 200) {
        var peers = request.responseText.split("\n");
        my_id = parseInt(peers[0].split(',')[1]);
        for (var i = 1; i < peers.length; ++i) {
          if (peers[i].length > 0) {
            var parsed = peers[i].split(',');
            other_peers[parseInt(parsed[1])] = parsed[0];
            if (parsed[0] == "ocupus_orchestrator")
              orchestrator = parseInt(parsed[1])            

          }
        }
        NProgress.done();
        startHangingGet();
        showConnected();        
        request = null;
      }
    }
  } catch (e) {
    NProgress.done();    
    showError("error: " + e.description);
  }
}

function signIn() {

  try {
    request = new XMLHttpRequest();
    request.onerror = function(e) {
      console.log(e);
      showError("An error occured connecting to the server");
      showDisconnected();
    }
    request.onreadystatechange = signInCallback;
    request.open("GET", server + "/sign_in?" + localName, true);
    request.send();
  } catch (e) {
    showError("error: " + e.description);
  }
}

function sendToPeer(peer_id, data) {
  var r = new XMLHttpRequest();
  r.open("POST", server + "/message?peer_id=" + my_id + "&to=" + peer_id,
         false);
  r.setRequestHeader("Content-Type", "text/plain");
  r.send(data);
  r = null;
}

function connect() {
  localName = "receiver";
  server = "http://" + window.location.hostname + ":8888";
  signIn();

}

function disconnect() {
  if (request) {
    request.abort();
    request = null;
  }
  
  if (hangingGet) {
    hangingGet.abort();
    hangingGet = null;
  }

  if (my_id != -1) {
    request = new XMLHttpRequest();
    request.open("GET", server + "/sign_out?peer_id=" + my_id, false);
    request.send();
    request = null;
    my_id = -1;
  }


}

function logLine(line) {
    $("<div />").html(line).appendTo("#log-information");
    tailScroll();
}

scrollTriggered = false;

function tailScroll() {
    if (!scrollTriggered) {
      scrollTriggered = true;
      setTimeout("animateScroll()", 100);
    }
}

function animateScroll() {
    var height = $("#log-information").get(0).scrollHeight;
    $("#log-information").animate({
        scrollTop: height
    }, 200);
    scrollTriggered = false;
}

window.onbeforeunload = disconnect;

$(document).ready(function() {
  NProgress.start();
  console.log("Connecting...");
  connect();


  $("#camera-panel").sortable({
    connectWith: "#camera-panel",
          handle: ".panel-heading"
      
    });

  $( "#camera-panel" ).on( "sortstop", function( event, ui ) {
    for (var s in streams) {
      $("#" + s).get(0).play();
    }
  });

  $("#reboot-button").click(systemReboot);
  $("#shutdown-button").click(systemShutdown);
});



var tx_data = d3.range(150).map(function() {return 0});

function chart(domain, interpolation, tick) {

  var margin = {top: 6, right: 0, bottom: 6, left: 80},
      width = 400,
      height = 120 - margin.top - margin.bottom;

  var x = d3.scale.linear()
      .domain(domain)
      .range([0, width]);

  var y = d3.scale.linear()
      .domain([0, 3])
      .range([height, 0]);

  var line = d3.svg.line()
      .interpolate(interpolation)
      .x(function(d, i) { return x(i); })
      .y(function(d, i) { return y(d); });

  var svg = d3.select("#traffic-graph").append("p").append("svg")
      .attr("width", width + margin.left + margin.right)
      .attr("height", height + margin.top + margin.bottom)
      .style("margin-left", -margin.left + "px")
    .append("g")
      .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

  svg.append("defs").append("clipPath")
      .attr("id", "clip")
    .append("rect")
      .attr("width", width)
      .attr("height", height);

  svg.append("g")
      .attr("class", "y axis")
      .call(d3.svg.axis().tickFormat(function(d) { return d.toFixed(1) + " mbps"; }).scale(y).ticks(5).orient("left"));

  var path = svg.append("g")
      .attr("clip-path", "url(#clip)")
    .append("path")
      .data([tx_data])
      .attr("class", "line")
      .attr("d", line);

  tick(path, line, tx_data, x);
}

chart([0, 150 - 1], "linear", function tick(path, line, tx_data, x) {

  // push a new data point onto the back
  tx_data.push(tx_delta_mbps);

  // redraw the line, and then slide it to the left
  path
      .attr("d", line)
      .attr("transform", null)
    .transition()
      .duration(1000)
      .ease("linear")
      .attr("transform", "translate(" + x(-1) + ")")
      .each("end", function() { tick(path, line, tx_data, x); });

  // pop the old data point off the front
  tx_data.shift();

});

