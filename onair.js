(function() {
	onair = {};
	$(document).delegate("#station", "pageinit", function() {
		console.log("Doing AJAX request for STATION "+ this.id);
		var midnight = new Date();
		midnight.setHours(0, 0, 0, 0);
		$.ajax({
			url: "http://api.stanwood.de/webservices/onair/android_0_7_0_de_programData/getPrograms.jsonp.php5",
			dataType: "jsonp",
			data: {
				startDate: midnight.getTime() / 1000 + - 2 * 60 * 60,
				endDate: midnight.getTime() / 1000 + (24 + 2) * 60 * 60 + 691200,
				stations: this.id
			},
			success: function(data) {
				console.log("Success");
				var $content = $("#content");
				var tmpl = " \
{{data}} \
  <li><a href='detail.html?{{id}}' id='{{id}}'> \
      <img src='{{if f|notempty}}{{iconBaseURL}}/{{f}}{{else}}data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=={{/if}}' class='onair-thumb'> \
      <h2>{{h1}}</h2> \
      {{if h2|notempty}} \
      <p>{{h2}}</p> \
      {{/if}} \
      <p class='ui-li-aside'><strong>{{s|time}}&nbsp;-&nbsp;{{e|time}}</strong></p> \
  </a></li> \
{{/data}} \
";
				$("#list1")
				.html(Mark.up(tmpl, {
					"data": data
				}, {
					globals: {
						iconBaseURL: "http://api.stanwood.de/images/programs/de"
					},
					pipes: {
						time: function(str) {
							var date = new Date(Number(str) * 1000);
							return date.getHours() + ':' + date.getMinutes();
						}
					}
				}))
				.listview("refresh");
				
			},
			error: function() {
				console.log("Error loading station data");
			}
		});
	});

	$(document).delegate("#all_stations", "pageinit", function() {
		console.log("Doing AJAX request for ALL STATIONS");
		$.ajax({
			url: "http://api.stanwood.de/webservices/onair/android_0_7_0_de_programData/getStations.jsonp.php5",
			dataType: "jsonp",
			success: function(data) {
				console.log("Success");
				var $content = $("#content");
				var tmpl = " \
{{data}} \
<li><a href='#station' data-url='{{id}}'><img src='{{iconBaseURL}}/bunt_{{f}}' class='ui-li-icon'> \
{{h1}}</a></li> \
{{/data}}";
				var $list1 = $("#list1");
				$list1.html(Mark.up(tmpl, {
					"data": data
				}, {
					"globals": {
						iconBaseURL: "http://api.stanwood.de/images/logos/de"
					}
				}));
				$list1.listview("refresh");
				
			},
			error: function() {
				console.log("Error loading station data");
			}
		});
	});

})();
