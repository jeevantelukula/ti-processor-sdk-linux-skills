import json
import subprocess
import sys

def send_request(proc, request):
    proc.stdin.write(json.dumps(request) + '\n')
    proc.stdin.flush()
    line = proc.stdout.readline()
    return line.strip()

proc = subprocess.Popen([sys.executable, 'server.py'],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        text=True)

# Initialize
init = {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}
resp = send_request(proc, init)
print("Initialize:", resp)

# Parse initialize response to get the result (optional)
try:
    init_resp = json.loads(resp)
    if 'result' in init_resp:
        print("Initialize OK")
except:
    pass

# List variants (to see if we get a device)
variants = {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ti_processor_sdk_docs_list_variants","arguments":{}}}
resp = send_request(proc, variants)
print("List variants response received")

# Parse the variants response to get the text
try:
    variants_resp = json.loads(resp)
    if 'result' in variants_resp:
        # The result is an object with content and structuredContent
        # Extract the text from content[0].text
        if 'content' in variants_resp['result'] and len(variants_resp['result']['content']) > 0:
            text = variants_resp['result']['content'][0]['text']
            # Parse the text as JSON (it's a JSON array)
            variants_data = json.loads(text)
            print(f"Found {len(variants_data)} variants")
            # Print first variant as example
            if variants_data:
                print("First variant:", json.dumps(variants_data[0], indent=2))
except Exception as e:
    print("Failed to parse variants response:", e)

# Search for GPIO
search = {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ti_processor_sdk_docs_search","arguments":{"query":"GPIO","device":"AM62X","os":"linux","version":"latest","source":"software-dl","max_results":5}}}
resp = send_request(proc, search)
print("Search response received")

try:
    search_resp = json.loads(resp)
    if 'result' in search_resp:
        if 'content' in search_resp['result'] and len(search_resp['result']['content']) > 0:
            text = search_resp['result']['content'][0]['text']
            results = json.loads(text)
            print(f"Search returned {len(results)} results")
            if results:
                first_path = results[0]['path']
                print("First path:", first_path)
            else:
                print("No results found")
                first_path = None
        else:
            print("No content in search result")
            first_path = None
    else:
        print("Error in search:", search_resp)
        first_path = None
except Exception as e:
    print("Failed to parse search:", e)
    first_path = None

if first_path:
    # Test list_page_assets on that path
    list_assets = {"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"ti_processor_sdk_docs_list_assets","arguments":{"path":first_path,"device":"AM62X","os":"linux","version":"latest","source":"software-dl"}}}
    resp = send_request(proc, list_assets)
    print("List assets response received")

    try:
        assets_resp = json.loads(resp)
        if 'result' in assets_resp:
            if 'content' in assets_resp['result'] and len(assets_resp['result']['content']) > 0:
                text = assets_resp['result']['content'][0]['text']
                assets_data = json.loads(text)
                # assets_data should be a dict with 'assets' and 'metadata'
                if isinstance(assets_data, dict) and 'assets' in assets_data:
                    print(f"List assets returned {len(assets_data['assets'])} assets")
                    if assets_data['assets']:
                        first_asset = assets_data['assets'][0]['path']
                        print("First asset path:", first_asset)
                    else:
                        print("No assets found")
                        first_asset = None
                else:
                    # Fallback: maybe it's just an array (old format)
                    if isinstance(assets_data, list):
                        print(f"List assets returned {len(assets_data)} assets (old format)")
                        if assets_data:
                            first_asset = assets_data[0]['path']
                            print("First asset path:", first_asset)
                        else:
                            first_asset = None
                    else:
                        print("Unexpected assets data format:", assets_data)
                        first_asset = None
            else:
                print("No content in list assets result")
                first_asset = None
        else:
            print("Error in list assets:", assets_resp)
            first_asset = None
    except Exception as e:
        print("Failed to parse list assets:", e)
        first_asset = None

    if first_asset:
        # Test get_asset on that asset
        get_asset = {"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"ti_processor_sdk_docs_get_asset","arguments":{"asset_path":first_asset,"device":"AM62X","os":"linux","version":"latest","source":"software-dl"}}}
        resp = send_request(proc, get_asset)
        print("Get asset response received")

        try:
            asset_resp = json.loads(resp)
            if 'result' in asset_resp:
                if 'content' in asset_resp['result'] and len(asset_resp['result']['content']) > 0:
                    text = asset_resp['result']['content'][0]['text']
                    # The asset tool returns a JSON string directly (not wrapped in content? Actually it does)
                    # Let's just print the text
                    print("Asset data (first 200 chars):", text[:200])
                else:
                    print("No content in asset result")
            else:
                print("Error in get asset:", asset_resp)
        except Exception as e:
            print("Failed to parse get asset:", e)

# Terminate the server
proc.terminate()
proc.wait()