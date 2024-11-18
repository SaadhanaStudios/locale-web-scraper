from flask import Flask, render_template, request, jsonify
import subprocess
import threading
import csv
import os

app = Flask(__name__)
scraper_process = None
output_log = []
input_file = 'ingestionsummary.csv'

def run_scraper(url, selectors):
    global scraper_process, output_log
    scraper_process = subprocess.Popen(
        ['python', 'scraper.py', url, selectors],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    for line in iter(scraper_process.stdout.readline, ''):
        output_log.append(line)
        if scraper_process.poll() is not None:
            break

def save_input(url, selectors):
    with open(input_file, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([url, selectors])

def load_inputs():
    inputs = []
    if os.path.exists(input_file):
        with open(input_file, 'r') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                inputs.append({'url': row[0], 'selectors': row[1]})
    return inputs

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run-scraper', methods=['POST'])
def run_scraper_route():
    global output_log
    output_log = []
    data = request.get_json()
    if data is None or 'url' not in data or 'selectors' not in data:
        return jsonify({'error': 'Invalid input data'}), 400
    url = data['url']
    selectors = data['selectors']
    save_input(url, selectors)
    threading.Thread(target=run_scraper, args=(url, selectors)).start()
    return jsonify(message='Scraper started!')

@app.route('/previous-inputs', methods=['GET'])
def previous_inputs():
    inputs = load_inputs()
    return jsonify(inputs=inputs)

@app.route('/get-output', methods=['GET'])
def get_output():
    return jsonify(output=output_log)

@app.route('/cancel-scraper', methods=['POST'])
def cancel_scraper():
    global scraper_process
    if scraper_process is not None:
        scraper_process.terminate()
        scraper_process = None
        return jsonify(message='Scraper cancelled!')
    else:
        return jsonify(message='No scraper process to cancel!')

if __name__ == '__main__':
    app.run(debug=True)
