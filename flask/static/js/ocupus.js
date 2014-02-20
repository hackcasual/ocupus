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

function handleServerNotification(data) {
  var parsed = data.split(',');
  if (parseInt(parsed[2]) != 0)
    other_peers[parseInt(parsed[1])] = parsed[0];
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

function isGoodCandidate(conn) {
  if ($("#dofilter").checked) {
    return conn.search("172.17") != -1;
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

function handlePeerMessage(peer_id, data) {
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
        description.sdp = setBitRate(description.sdp, 2048);
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
      };

      localConnections[peer_id] = localPeerConnection;

    }  

    if (data.search("candidate") != -1 && isGoodCandidate(data)) {
      var candidateInfo = JSON.parse(data);
      var cand = new RTCIceCandidate(candidateInfo);

      localConnections[peer_id].addIceCandidate(new RTCIceCandidate(candidateInfo));

      didIt = true;
    } 
}

function GetIntHeader(r, name) {
  var val = r.getResponseHeader(name);
  return val != null && val.length ? parseInt(val) : -1;
}

function showConnected() {
  $("li.connection-status").html('<div class="connection-text">Connected</div><div class="fa fa-link fa-2x" style="color: white;">');
}

function showDisconnected() {
  $("li.connection-status").html('<div class="connection-text">No Connection</div><div class="fa fa-unlink fa-2x" style="color: white;">');
}


function showError(status) {
          $("#alerts").append('<div class="alert alert-danger" data-dismiss="alert">' + status + '</div>');
}

function hangingGetCallback() {

    if (hangingGet.readyState != 4)
      return;
    if (hangingGet.status != 200) {
      showError(hangingGet.statusText);
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

function startHangingGet() {
  try {
    hangingGet = new XMLHttpRequest();
    hangingGet.onreadystatechange = hangingGetCallback;
    hangingGet.ontimeout = onHangingGetTimeout;
    hangingGet.open("GET", server + "/wait?peer_id=" + my_id, true);
    hangingGet.send();  
  } catch (e) {
    showError(e.description);
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
  NProgress.done();
  console.log(request);
  showConnected();
  try {
    if (request.readyState == 4) {
      if (request.status == 200) {
        var peers = request.responseText.split("\n");
        my_id = parseInt(peers[0].split(',')[1]);
        for (var i = 1; i < peers.length; ++i) {
          if (peers[i].length > 0) {
            var parsed = peers[i].split(',');
            other_peers[parseInt(parsed[1])] = parsed[0];
          }
        }
        startHangingGet();
        request = null;
      }
    }
  } catch (e) {
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
  if (my_id == -1) {
    alert("Not connected");
    return;
  }
  if (peer_id == my_id) {
    alert("Can't send a message to oneself :)");
    return;
  }
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

window.onbeforeunload = disconnect;

$(document).ready(function() {
  var hashConf = getHashParams();
  if (typeof(hashConf['server']) !== 'undefined') {
    $("#server").attr("value",hashConf['server']);
  }

  if (typeof(hashConf['restrict']) !== 'undefined' && hashConf['restrict'] == "y") {
    $("#dofilter").prop('checked', true);
  }

  if (typeof(hashConf['auto']) !== 'undefined' && hashConf['auto'] == "y") {
    connect();
  }

  NProgress.start();
  connect();
});