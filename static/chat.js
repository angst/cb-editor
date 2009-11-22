// Copyright 2009 FriendFeed
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may
// not use this file except in compliance with the License. You may obtain
// a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
// WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
// License for the specific language governing permissions and limitations
// under the License.

$(document).ready(function() {
  if (!window.console) window.console = {};
  if (!window.console.log) window.console.log = function() {};

  $("#codearea").live("keyup", function(e) {
                        updater.send($(this));
                      });
  updater.poll();
});

function getCookie(name) {
  var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
  return r ? r[1] : undefined;
}

jQuery.postJSON = function(url, args, callback) {
  args._xsrf = getCookie("_xsrf");
  $.ajax({url: url, data: $.param(args), dataType: "text", type: "POST",
    success: function(response) {
      if (callback) callback(response);
    }, error: function(response) {
      console.log("ERROR:", response);
    }});
};

var updater = {
  errorSleepTime: 500,
  sig: null,
  body: null,

  poll: function() {
    var args = {"_xsrf": getCookie("_xsrf")};
    if (updater.sig) args.sig = updater.sig;
    $.ajax({url: "/a/text/listen", type: "POST", dataType: "text",
            data: $.param(args), success: updater.onSuccess,
            error: updater.onError});
  },

  send: function(textarea) {
    var val = textarea.val();
    if (updater.body != val) {
      $.ajax({url: "/a/text/update",
              data: $.param({body: val, _xsrf: getCookie("_xsrf")}),
              type: "POST",
              dataType: "text"});
    }
  },

  onSuccess: function(response) {
    console.log(response);
    try {
      updater.updateCode(eval("(" + response + ")"));
    } catch (e) {
      updater.onError();
      return;
    }
    updater.errorSleepTime = 500;
    window.setTimeout(updater.poll, 0);
  },

  onError: function(response) {
    updater.errorSleepTime *= 2;
    console.log("Poll error; sleeping for", updater.errorSleepTime, "ms");
    window.setTimeout(updater.poll, updater.errorSleepTime);
  },

  updateCode: function(text) {
    $('#codearea').text(text.body);
    updater.sig = text.sig;
    updater.body = text.body;
  }
};
