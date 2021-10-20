window.addEventListener('load', function () {
  username = document.getElementById('username').value
  user_hash = document.getElementById('user_hash').value

  Vue.use(Vuex)

  const store = new Vuex.Store({
    state: {
      connection: null,
      messages_list: [],
      connected: false,
      not_sended_messages: [],
      not_sended_shots: [],
      cells: [],
      selected_cells: [],
      enemy_cells_: [],
      miss_cells: [],
      hit_cells: [],
      your_hits: [],
      to_you_miss_cells: [],
      enemy: null,
    },

    mutations: {
      connecting(state) {
        state.connection = null;
        state.connection = new WebSocket('ws://' +
          'localhost:8000' +
          '/ws/game/' +
          '?' +
          'username=' + username +
          '&' + 'user_hash=' + user_hash);

        state.connection.onopen = () => {
          state.connected = true;
          state.cells = Object.keys(app.$refs);
        };

        state.connection.onerror = () => {
          state.connected = false;
          state.connection = null;
        };

        state.connection.onclose = () => {
          app.game_started = false;
          app.player_ready = false;
          app.room_guest = null;
          state.connection.close();
          state.connection = null;
          state.messages_list = [];
          state.selected_cells = [];
        };

        state.connection.onmessage = (message_event) => {
          let message = JSON.parse(message_event.data);
          if (message.context === 'connect') {
            app.room_member = message.data.room_member;
            app.room_guest = message.data.room_guest;
            state.messages_list = JSON.parse(message.data.messages)
            if (message.data.hasOwnProperty(username + ":selected_cells")) {
              state.selected_cells = JSON.parse(message.data[username + ":selected_cells"]);
              app.player_ready = true;

              function gamestatus() {
                for (let key in state.selected_cells) {
                  app.$refs[state.selected_cells[key]][0].style.background = "blue"
                }
                if (message.data.hasOwnProperty('game_status')) {
                  app.game_started = true;
                  if (message.data['room_member'] === username) {
                    state.enemy = message.data['room_guest'];
                  } else {
                    state.enemy = message.data['room_member'];
                  }
                  let acces = message.data[username + ":access_to_shot"];
                  if (acces === 'true') {
                    app.access_to_shot = true;
                  }
                }
              }
              setTimeout(gamestatus, 50);

            }
            if (message.data.hasOwnProperty(username + ":miss_cells")) {
              state.miss_cells = JSON.parse(message.data[username + ":miss_cells"]);

              function miss_cells() {
                for (let key in state.miss_cells) {
                  app.$refs['enemy_' + state.miss_cells[key]][0].style.background = "black"
                }
              }
              setTimeout(miss_cells, 50);

            }
            if (message.data.hasOwnProperty(username + ":dead_cells")) {
              state.your_misses = JSON.parse(message.data[username + ":dead_cells"]);

              function your_misses() {
                for (let key in state.your_misses) {
                  let ref = state.your_misses[key]
                  app.$refs[state.your_misses[key]][0].style.background = "red"
                }
              }
              setTimeout(your_misses, 50);

            }

            function zzzz() {
              state.to_you_miss_cells = JSON.parse(message.data[state.enemy + ":miss_cells"]);
              for (let key in state.to_you_miss_cells) {
                app.$refs[state.to_you_miss_cells[key]][0].style.background = "black"
              }
            }
            setTimeout(zzzz, 50);

            if (message.data.hasOwnProperty(username + ":hit_cells")) {
              state.hit_cells = JSON.parse(message.data[username + ":hit_cells"]);

              function hit_cells() {
                for (let key in state.hit_cells) {
                  app.$refs['enemy_' + state.hit_cells[key]][0].style.background = "red"
                }
              }
              setTimeout(hit_cells, 50);

            }
            var not_sended_messages_length = state.not_sended_messages.length;
            if (not_sended_messages_length > 0) {
              for (var i = 0; i < not_sended_messages_length; i++) {
                state.connection.send(JSON.stringify({
                  'context': 'send_message',
                  'message': state.not_sended_messages[i]
                }));
                state.not_sended_messages.splice(i, 1);
              }
            }
          } else if (message.context === 'message') {
            state.messages_list.push(message.message)
          } else if (message.context === 'notification') {
            if (message.type === 'start_game') {
              app.access_to_shot = true;
              app.game_started = true;
              if (message.data['room_member'] === username) {
                state.enemy = message.data['room_guest'];
              } else {
                state.enemy = message.data['room_member'];
              }
            } else if (message.type === 'exit_room') {
              app.access_to_shot = false;
              app.game_started = false;
              app.player_ready = false;
              app.room_guest = null;
              state.connection.close();
              state.connection = null;
              state.messages_list = [];
              for (let key in state.hit_cells) {
                app.$refs[state.hit_cells[key]][0].style.background = ""
              }
              for (let key in state.miss_cells) {
                app.$refs['enemy_' + state.miss_cells[key]][0].style.background = ""
              }
              for (let key in state.your_hits) {
                app.$refs['enemy_' + state.your_hits[key]][0].style.background = ""
              }
              state.selected_cells = [];
            };
          } else if (message.context === 'action') {
            if (message.action_type === 'hit') {
              if ((message.params.split(',')).includes(username)) {
                let cell = message.params.split(',')[1]
                app.$refs[cell][0].style.background = "red"
                app.access_to_shot = true;
              } else {
                let cell = 'enemy_' + message.params.split(',')[1]
                app.$refs[cell][0].style.background = "red"
              };
            } else if (message.action_type === 'miss') {
              if ((message.params.split(',')).includes(username)) {
                let cell = 'enemy_' + message.params.split(',')[1]
                app.$refs[cell][0].style.background = "black"
              } else {
                let cell = message.params.split(',')[1]
                app.$refs[cell][0].style.background = "black"
                app.access_to_shot = true;
              };
            } else if (message.action_type === 'lose') {
              store.state.connection.send(JSON.stringify({
                'context': 'exit_room'
              }));
              this.room_guest = null;
              store.state.connection.close();
            };
          };
        };
      },

      disconnecting(state) {
        state.connection.close();
      },
    },

    actions: {
      connect({
        commit
      }) {
        if (this.state.connection === null) {
          commit('connecting');
        };
      },
    },
  });

  var app = new Vue({
    el: '#app',

    store: store,

    data: {
      user: username,
      message: null,
      x: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'],
      y: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
      game_started: false,
      room_member: null,
      room_guest: null,
      player_ready: false,
      access_to_shot: false,
    },
    computed: {
      messages_list: function () {
        return this.$store.state.messages_list
      },
      selected_cells: function () {
        return 20 - this.$store.state.selected_cells.length;
      },
    },
    methods: {
      setShipPosition: function (e) {
        if (this.player_ready === false) {
          if (this.$store.state.selected_cells.length < 20) {
            if (this.$store.state.selected_cells.includes(e)) {
              let index = this.$store.state.selected_cells.indexOf(e);
              this.$store.state.selected_cells.splice(index, 1);
              this.$refs[e][0].style.background = ""
            } else {
              this.$store.state.selected_cells.push(e)
              this.$refs[e][0].style.background = "blue"
            }
          } else {
            this.player_ready = true
            this.$store.state.connection.send(JSON.stringify({
              'context': 'player_ready',
              'selected_cells': this.$store.state.selected_cells
            }));
          }
        }
      },
      exitRoom: function (e) {
        e.preventDefault();
        this.$store.state.connection.send(JSON.stringify({
          'context': 'exit_room'
        }));
        this.room_guest = null;
        this.$store.state.connection.close();
      },
      findRoom: function (e) {
        e.preventDefault();
        try {
          this.$store.state.connection.close();
        } catch {
          this.$store.state.connection = null;
        }
        this.$store.dispatch('connect');
      },
      sendMessage: function (e) {
        e.preventDefault();
        try {
          this.$store.state.connection.send(JSON.stringify({
            'context': 'send_message',
            'message': this.message
          }));
        } catch {
          while (true) {
            try {
              this.$store.state.connection.close();
            } catch {
              this.$store.state.connection = null;
            }
            try {
              this.$store.dispatch('connect');
              break;
            } catch {
              this.$store.state.connection = null;
            }
          }
        }
      },
      shot: function (e) {
        try {
          if (this.access_to_shot) {
            this.access_to_shot = false;
            this.$store.state.connection.send(JSON.stringify({
              'context': 'shot',
              'user': this.username,
              'cell': e
            }));
          }
        } catch {
          while (true) {
            try {
              this.$store.state.connection.close();
            } catch {
              this.$store.state.connection = null;
            }
            try {
              this.$store.dispatch('connect');
              break;
            } catch {
              this.$store.state.connection = null;
            }
          }
        }
      },

    },


  });

})