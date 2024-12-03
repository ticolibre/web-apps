import os
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
import re

# Step 1: Parse sitemap to get all post and page URLs
sitemap_url = "http://localhost:10003/wp-sitemap.xml"
response = requests.get(sitemap_url)

if response.status_code != 200:
    raise Exception(f"Failed to fetch sitemap: {sitemap_url}")

# Parse the sitemap XML
root = ET.fromstring(response.content)
namespace = {'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
urls = []

# Fetch URLs from the sitemap and sub-sitemaps
for sitemap in root.findall('sitemap:sitemap', namespace):
    loc = sitemap.find('sitemap:loc', namespace).text
    sitemap_response = requests.get(loc)
    sitemap_tree = ET.fromstring(sitemap_response.content)
    for url in sitemap_tree.findall('sitemap:url', namespace):
        loc_url = url.find('sitemap:loc', namespace).text
        urls.append(loc_url)

print(f"Found {len(urls)} pages/posts to analyze...")

# Step 2: Extract all image URLs from each post/page
image_urls_in_use = set()

# Regular expression pattern to match image URLs
image_pattern = re.compile(r'https?://localhost:10003/wp-content/uploads/.*?\.(?:png|jpg|jpeg|gif|webp)', re.IGNORECASE)

for url in urls:
    page_response = requests.get(url)
    if page_response.status_code != 200:
        print(f"Failed to fetch {url}")
        continue
    
    # Parse the HTML content of the page
    soup = BeautifulSoup(page_response.content, 'html.parser')
    
    # Get the entire HTML content as text
    html_content = soup.decode_contents()

    # Find all matches for the image pattern in the HTML content
    matches = image_pattern.findall(html_content)
    image_urls_in_use.update(matches)  # Add all found matches to the set

print(f"Found {len(image_urls_in_use)} unique images in posts/pages.")

# Step 3: List all image files in the uploads directory
uploads_dir = "/Users/TicoLibre/Local Sites/irr/app/public/wp-content/uploads"
all_images_on_disk = set()

for root_dir, dirs, files in os.walk(uploads_dir):
    for file_name in files:
        if file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            full_path = os.path.join(root_dir, file_name)
            # Convert local file path to a web URL for comparison
            relative_path = os.path.relpath(full_path, uploads_dir)
            image_url = f"http://localhost:10003/wp-content/uploads/{relative_path.replace(os.sep, '/')}"
            all_images_on_disk.add(image_url)

print(f"Found {len(all_images_on_disk)} images on disk.")

# Step 4: Compare and find unused images
unused_images = all_images_on_disk - image_urls_in_use

# Step 5: Save found images and unused images to separate files
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")

# File for images found in posts/pages
found_images_file = os.path.join(desktop_path, "found_images.txt")
with open(found_images_file, 'w') as f:
    for image in sorted(image_urls_in_use):
        f.write(f"{image}\n")

# File for unused images
unused_images_file = os.path.join(desktop_path, "unused_images.txt")
with open(unused_images_file, 'w') as f:
    for image in sorted(unused_images):
        f.write(f"{image}\n")

print(f"Found images saved to {found_images_file}.")
print(f"Unused images saved to {unused_images_file}.")

# Step 6: Ask for confirmation to delete unused images
if unused_images:
    print(f"\nFound {len(unused_images)} unused images.")
    confirm = input("Do you want to proceed to delete these unused images from the uploads folder? (yes/no): ").strip().lower()

    if confirm == 'yes':
        for image in unused_images:
            try:
                os.remove(image.replace("http://localhost:10003/", "/Users/TicoLibre/Local Sites/irr/app/public/"))
                print(f"Deleted: {image}")
            except Exception as e:
                print(f"Failed to delete {image}: {e}")
    else:
        print("No images were deleted.")
else:
    print("No unused images found.")

# Step 7: Ask for confirmation to delete empty folders in the uploads directory
def delete_empty_folders(path):
    for dirpath, dirnames, filenames in os.walk(path, topdown=False):
        if not os.listdir(dirpath):  # Check if the directory is empty
            try:
                os.rmdir(dirpath)
                print(f"Deleted empty folder: {dirpath}")
            except OSError as e:
                print(f"Failed to delete folder {dirpath}: {e}")

confirm_empty_folders = input("Do you want to proceed to delete empty folders in the uploads directory? (yes/no): ").strip().lower()
if confirm_empty_folders == 'yes':
    delete_empty_folders(uploads_dir)
else:
    print("No empty folders were deleted.")

print("Finished checking and deleting empty folders.")
