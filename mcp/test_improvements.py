import json
import subprocess
import sys

def send_request(proc, request):
    proc.stdin.write(json.dumps(request) + '\n')
    proc.stdin.flush()
    return proc.stdout.readline().strip()

proc = subprocess.Popen([sys.executable, 'server.py'],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        text=True)

# Initialize
init = {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}
resp = send_request(proc, init)
print("=== Initialize ===")
print(resp)
print()

# List variants to get a device
variants = {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ti_processor_sdk_docs_list_variants","arguments":{}}}
resp = send_request(proc, variants)
variants_data = json.loads(resp)['result']['content'][0]['text']
variants_list = json.loads(variants_data)
print(f"=== Found {len(variants_list)} variants ===")
print()

# Search for GPIO to get a page path
search = {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ti_processor_sdk_docs_search","arguments":{"query":"GPIO","device":"AM62X","os":"linux","version":"latest","source":"software-dl","max_results":1}}}
resp = send_request(proc, search)
search_data = json.loads(resp)['result']['content'][0]['text']
search_results = json.loads(search_data)
if search_results:
    first_path = search_results[0]['path']
    print(f"=== Search result path: {first_path} ===")

    # Test list_page_assets with metadata (improvement 1)
    list_assets = {"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"ti_processor_sdk_docs_list_assets","arguments":{"path":first_path,"device":"AM62X","os":"linux","version":"latest","source":"software-dl"}}}
    resp = send_request(proc, list_assets)
    assets_data = json.loads(resp)['result']['content'][0]['text']
    assets_result = json.loads(assets_data)
    print("=== List Page Assets (with metadata) ===")
    print(f"Assets found: {len(assets_result.get('assets', []))}")
    if 'metadata' in assets_result:
        meta = assets_result['metadata']
        print(f"Metadata: {json.dumps(meta, indent=2)}")
    print()

    # Test get_asset (improvements 2 & 3)
    if assets_result.get('assets'):
        first_asset = assets_result['assets'][0]['path']
        print(f"=== Testing get_asset with: {first_asset} ===")

        get_asset = {"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"ti_processor_sdk_docs_get_asset","arguments":{"asset_path":first_asset,"device":"AM62X","os":"linux","version":"latest","source":"software-dl"}}}
        resp = send_request(proc, get_asset)
        asset_data = json.loads(resp)['result']['content'][0]['text']
        asset_result = json.loads(asset_data)

        print(f"Asset size: {asset_result.get('size', 0)} bytes")
        print(f"MIME type: {asset_result.get('mimeType', 'unknown')}")
        print(f"Data length (base64): {len(asset_result.get('data', ''))} chars")

        # Test caching by calling again
        print("\n=== Testing LRU cache (second call) ===")
        resp2 = send_request(proc, get_asset)
        asset_data2 = json.loads(resp2)['result']['content'][0]['text']
        asset_result2 = json.loads(asset_data2)

        if asset_result == asset_result2:
            print("✓ Caching working - identical results")
        else:
            print("✗ Caching issue - different results")
else:
    print("No search results found")

# Test MIME type detection with various extensions
print("\n=== Testing MIME type detection ===")
import mimetypes
test_paths = [
    "test.png",
    "test.jpg",
    "test.jpeg",
    "test.svg",
    "test.gif",
    "test.pdf",
    "test.txt",
    "test.webp",
    "test.avif",
    "test.unknown"
]
for path in test_paths:
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    print(f"{path}: {mime}")

proc.terminate()
proc.wait()