import socket, ssl, datetime, json, time, re, sqlite3, random, requests, traceback
from functions import get_sender, get_message, get_name, get_random_joke, react_leet, print_split_lines, \
    update_streak_graph
from xml.etree import ElementTree as ET
from urlshortener import shorten_url


class bot:
    def __init__(self, host, port, nick, ident, realname, master, channel):
        self.host = host
        self.port = port
        self.nick = nick
        self.ident = ident
        self.realname = realname
        self.master = master
        self.channel = channel
        self.sock = socket.socket()
        self.s = None
        self.leets = []
        self.score = {}
        self.errors = 0

    def load_leet_log(self):
        try:
            with open("leetlog/" + self.host + '.json') as data_file:
                self.score = json.load(data_file)
                print("Score for: " + self.host + "  " + str(self.score))
        except:
            print("Error: Loading leet log.")

    def connect_to_server(self):
        self.s = ssl.wrap_socket(self.sock)
        self.s.connect((self.host, self.port))

        self.s.send(bytes("NICK {}\r\n".format(self.nick), "UTF-8"))
        self.s.send(bytes("USER {} {} bla :{}\r\n".format(self.ident, self.host, self.realname), "UTF-8"))

    def respond_to_ping(self, lines):
        for line in lines:
            line = str.rstrip(line)
            line = str.split(line)
            if line[0] == "PING":
                self.s.send(bytes("PONG {}\r\n".format(line[1]), "UTF-8"))

    def join_channel(self, msg):
        try:
            if len(msg):
                if "PRIVMSG" not in msg[0] and "PING" not in msg[0]:
                    print(msg[0])
                    self.s.send(bytes("JOIN {}\r\n".format(self.channel), "UTF-8"))
        except IndexError:
            print(msg)
            if self.errors < 5:
                self.errors = self.errors + 1
                print('Error trying to join channel.. number of errors: ' + str(self.errors))
            else:
                self.connect_to_server()
                print('Attempting to reconnect..')

    def respond_hello(self, m, nick, sender):
        try:
            words = m.split(" ")
            if words[0].lower() == "hello" or m == 'hello\r':
                self.s.send(bytes("PRIVMSG {} :Hello, {}\r\n".format(sender, nick), "UTF-8"))
        except (AttributeError, IndexError):
            return ""

    def respond_roll(self, msg, nick, respondTo):
        try:
            words = [""]
            if " " in msg:
                words = msg.split(" ")
            if msg == '!roll\r':
                self.s.send(
                    bytes("PRIVMSG {} :{} rolled: {} (1 - 100)\n\r".format(respondTo, nick, random.randint(1, 100)),
                          "UTF-8"))
            elif words[0] == "!roll":
                self.s.send(bytes("PRIVMSG {} :{} rolled: {} ({} - {})\n\r".format(respondTo, nick, random.randint(
                    int(words[1]), int(words[2].split('\r')[0])), words[1], words[2]), "UTF-8"))
        except:
            print('Error rolling.')

    def update_score(self, nick):
        if nick not in self.score:
            self.score[nick] = {'score': 1, 'streak': 1}
        else:
            self.score[nick]['score'] += 1
            self.score[nick]['streak'] += 1

    def check_streak(self, unique_list):
        for nick in self.score:
            if nick not in unique_list:
                self.score[nick]['streak'] = 0

    def send_leet_masters(self, masters):
        s = self.s
        last = (len(masters) - 1)
        congr = "Leet masters today: "
        current = 0
        if len(self.leets):
            for person in masters:
                if len(masters) == 1:
                    congr = "{} was the only leet master today... disappointing.".format(self.leets[0])
                elif current < last:
                    congr += "{}, ".format(person)
                elif current == last:
                    congr += "and {}.".format(person)
                current += 1
            s.send(bytes("PRIVMSG {} :{}\n\r".format(self.channel, congr), "UTF-8"))
            s.send(bytes("PRIVMSG {} :Everyone else, shaaaaaame!\n\r".format(self.channel), "UTF-8"))
        elif len(self.leets) == 0:
            s.send(
                bytes("PRIVMSG {} :Noone remembered Leet! Shame on everyone! Shaaaame!\n\r".format(self.channel),
                      "UTF-8"))
            print(self.score)

    def log_winners(self):
        print(self.score)
        uniquelist = list(set(self.leets))
        self.check_streak(uniquelist)
        for person in uniquelist:
            self.update_score(person)

        self.send_leet_masters(uniquelist)

        with open("leetlog/" + self.host + '.json', 'w+') as outfile:
            json.dump(self.score, outfile)
        update_streak_graph("leetlog/" + self.host + '.graph.json', "leetlog/" + self.host + '.json', uniquelist)
        self.leets = []
        print(self.score)

    def send_random_joke(self, msg, sender):
        try:
            if "!joke" in msg:
                self.s.send(
                    bytes("PRIVMSG {} :{}\n\r".format(sender, get_random_joke()), "UTF-8"))
        except TypeError:
            print()

    def check_time(self):
        while 1:
            d = datetime.datetime.now()
            if (d.hour == 13) and (d.minute == 38) and (d.second == 5):
                self.log_winners()
                time.sleep(5)
            time.sleep(1)

    def send_urls(self, message, sender):
        try:
            url_string = ""
            urls = []
            words = [""]
            if " " in message:
                words = message.split(" ")
            if "!urls" in message and len(words) < 2:
                conn = sqlite3.connect('db.sqlite')
                cursor = conn.cursor()
                cursor.execute('SELECT url FROM urls WHERE hostname = ? AND sender = ? ORDER BY id DESC LIMIT 5;',
                               (self.host, sender))

                url_string = "The 5 last urls: "
                urls = cursor.fetchall()
                print(urls)
                if not len(urls):
                    urls = [("", " nothing to show.")]
                conn.close()
            elif words[0] == "!urls":
                nick = words[1].strip()
                conn = sqlite3.connect('db.sqlite')
                cursor = conn.cursor()
                cursor.execute('SELECT url FROM urls WHERE nick = ? AND hostname = ? AND sender = ? ORDER BY id DESC LIMIT 5;',
                               (nick, self.host, sender))
                url_string = "The 5 last urls from " + nick + ":"
                urls = cursor.fetchall()
                if not len(urls):
                    urls = [("", " nothing to show.")]
                conn.close()
            current = 1
            if len(urls):
                for s in urls:
                    if len(urls) != current:
                        current += 1
                        url_string += s[0] + ", "
                    else:
                        url_string += s[0] + "."
                self.s.send(
                    bytes("PRIVMSG {} :{}\n\r".format(sender, url_string), "UTF-8"))
        except Exception as e:
            print(self.host)
            print(traceback.format_exc())

    def log_urls(self, input_string, sender, nick):
        urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                          str(input_string))
        if len(urls):
            try:
                conn = sqlite3.connect('db.sqlite')
                cursor = conn.cursor()
                for url in urls:
                    date = datetime.datetime.now().strftime("%d/%m/%Y")
                    if len(url) > 100:
                        short_url = shorten_url(url)
                        cursor.execute("INSERT INTO urls (url, nick, added_date, hostname, sender) VALUES (?,?,?,?,?);",
                                       (short_url, nick, date, self.host, sender))
                    else:
                        cursor.execute("INSERT INTO urls (url, nick, added_date, hostname, sender) VALUES (?,?,?,?,?);",
                                       (url, nick, date, self.host, sender))
                conn.commit()
            except Exception as e:
                print(e)
                print("Error logging urls")

    def fetch_weather_forecast(self, sender, message):
        if "!forecast" in message:
            r = requests.get("http://www.yr.no/place/Norway/Hordaland/Bergen/Bergen/forecast_hour_by_hour.xml")
            root = ET.fromstring(r.content)

            next_hour = root.find('forecast').find('tabular')[0]
            from_time = next_hour.attrib['from']
            to_time = next_hour.attrib['to']
            temp = next_hour.find('temperature').attrib['value']
            temp_unit = next_hour.find('temperature').attrib['unit']
            wind_direction = next_hour.find('windDirection').attrib['name']
            wind_speed = next_hour.find('windSpeed').attrib['name']

            self.s.send(bytes("PRIVMSG {} :Forecast from {} to {}\n\r".format(sender, from_time, to_time), "UTF-8"))
            self.s.send(bytes(
                "PRIVMSG {} :Temp: {} WindDirection: {} WindSpeed: {}".format(sender, (temp + " " + temp_unit),
                                                                              wind_direction, wind_speed), "UTF-8"))

    def convert_long_url(self, message, sender):
        try:
            words = message.split(" ")
            if words[0] == "!u":
                short_url = shorten_url(words[1])
                self.s.send(
                    bytes("PRIVMSG {} :{}\n\r".format(sender, "Your short url: " + short_url), "UTF-8"))
        except Exception as e:
            print(e)

    def fetch_course_info(self, sender, message):
        if "!exam" in message:
            try:
                code = message.split(" ")[1].strip().upper()
                self.respond(sender, "https://eksamen.lillevik.pw/?course=" + code)
            except Exception as e:
                self.respond(sender, "Error finding course...")
                print(traceback.format_exc())

    def respond(self, sender, message):
        self.s.send(
            bytes("PRIVMSG {} :{}\n\r".format(sender, message), "UTF-8"))

    def run_bot(self):
        readbuffer = ""
        self.connect_to_server()
        self.load_leet_log()
        while 1:
            readbuffer = readbuffer + self.s.recv(1024).decode("UTF-8")
            temp = readbuffer.split("\n")
            readbuffer = temp.pop()
            print_split_lines(temp)

            self.respond_to_ping(temp)
            self.join_channel(temp)

            nick = str(get_name(temp))
            message = str(get_message(temp))
            sender = str(get_sender(temp, nick))

            self.respond_hello(message, nick, sender)
            react_leet(message, self.leets, nick)
            self.respond_roll(message, nick, sender)
            self.send_random_joke(message, sender)
            self.log_urls(message, sender, nick)
            self.send_urls(message, sender)
            self.convert_long_url(message, sender)
            self.fetch_weather_forecast(sender, message)
            self.fetch_course_info(sender, message)
