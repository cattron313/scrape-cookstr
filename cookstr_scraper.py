#zazu workfile
import mongohelpers
import models

import urllib2
import sys
import re
import bs4
import Queue
from bs4 import BeautifulSoup

html_parser_name = "lxml"
base_url = "http://www.cookstr.com"
#empty search url sorts the results by newest first
empty_search_url = "/searches?query=&cal=&sod=&carb=&cal_fat=&cal_sat_fat=&fib=&by=&sort=created_at"
pages_already_visited = []
num_recipes = 0

# Uses a queue to keep track of pages it needs to visit.  Performs a page_scrape
# on the search page urls in the queue
def full_scrape():
	if sys.flags.debug:
		print "BEGIN FULL SCRAPE OF SITE..."
	queue_of_pages = Queue.Queue()
	page_scrape(base_url + empty_search_url, queue_of_pages)
	while (not queue_of_pages.empty()):
		url_componet = queue_of_pages.get()
		page_scrape(base_url + url_componet, queue_of_pages)

	if sys.flags.debug:
		print '^_^ YOU HAVE JUST SCRAPED COOKSTR.COM\nHEH...THOSE BITCHES.'


# Takes a search page url and scrapes it for recipe urls and other
# search page urls. 
def page_scrape(complete_page_url, queue):
	if sys.flags.debug:
		print "BEGIN FULL SCRAPE OF PAGE..."

	search_page_html = urllib2.urlopen(complete_page_url).read()
	soup = BeautifulSoup(search_page_html, html_parser_name)

	#retrieve tags from html
	recipe_urls = soup("div", "image-wrapper")
	page_urls = soup("div", "pagination")

	if sys.flags.debug:
		print "TAG_RECIPE_URLS: ", recipe_urls
		print "TAG_PAGE_URLS: ", page_urls

	#extract text from tags
	recipe_url_text = extract_text_for_recipe_url(recipe_urls)
	page_url_text = extract_text_for_page_url(page_urls)

	if sys.flags.debug:
		print "TEXT_RECIPE_URLS: ", recipe_url_text
		print "TEXT_PAGE_URLS: ", page_url_text

	for url_componet in page_url_text:
		if sys.flags.debug:
			print "PAGE_URL: " + base_url + url_componet
		queue.put(url_componet)

	for url_componet in recipe_url_text:
		if sys.flags.debug:
			print "RECIPE_URL: " + base_url + url_componet
		scrape_url(base_url + url_componet)


# Current site is structured <div class=image-wrapper>
# <a href=[recipe_url]><img/></a></div>
def extract_text_for_recipe_url(recipe_urls):
	array = []
	for wrapper in recipe_urls:
		obj = wrapper.contents[0]
		if isinstance(obj, bs4.element.Tag):
			#based on the current sructure of the site,
			#we know that if object is a tag, it is an <a>
			array.append(obj["href"])
	return array

# Gets all the urls for the page link bar at the bottom.
# Checks to see if they have already been visited before
# returning them.
def extract_text_for_page_url(page_urls):
	array = []
	for obj in page_urls[0]:
		if isinstance(obj, bs4.element.Tag) and does_have_attribute(obj, "href") and not obj["href"] in pages_already_visited:
			pages_already_visited.append(obj["href"])
			array.append(obj["href"])
	return array

def does_have_attribute(tag, query):
	for attr in tag.attrs:
		if query.lower() == attr.lower():
			return True
	return False



# Takes a recipe url and scrapes it for model data.
def scrape_url(url):
	if sys.flags.debug:
		print "BEGIN SCRAPE OF RECIPE..."

	html = urllib2.urlopen(url).read()
	soup = BeautifulSoup(html, html_parser_name)
	
	#scrape tags from html
	name = soup(id="recipe_title")
	ingredients = soup(itemprop="ingredients")
	directions = soup("div", "recipe_attr_text")
	time = soup("time")
	servings = soup(itemprop="recipeYield")
	nutrients = soup("div", "nutrient")

	
	if sys.flags.debug:
		print "TAG_SOURCE_ID: " + url
		print "TAG_NAME: ", name
		print "TAG_INGREDIENTS:", ingredients
		print "TAG_DIRECTIONS: ", directions
		print "TAG_TIME: ", time
		print "TAG_SERVINGS: ", servings
		print "TAG_NUTRIENTS: ", nutrients
	
	#extract text from tags	
	source_id_txt = extract_text_for_source_id(url)
	name_txt = extract_text_for_name(name)
	ingredient_text = extract_text_for_ingredients(ingredients)
	direction_text = extract_text_for_directions(directions)
	time_text = extract_text_for_time(time)
	if len(servings) > 0:
		serving_text = extract_text_for_servings(servings)
	if len(nutrients) > 0:
		nutrient_text = extract_text_for_nutrients(nutrients)
	
	if sys.flags.debug:
		print "TEXT_SOURCE_ID: ", source_id_txt
		print "TEXT_NAME: ", name_txt
		print "TEXT_INGREDIENTS: ", ingredient_text
		print "TEXT_DIRECTIONS: ", direction_text
		print "TEXT_TIME: ", time_text
		if len(servings) > 0:
			print "TEXT_SERVINGS: ", serving_text
		if len(nutrients) > 0:
			print "TEXT_NUTRIENTS: ", nutrient_text
		
	#put results in model
	entry, status = mongohelpers.spawn_entry(models.CookstrEntry, "source_id", source_id_txt)
	entry.name = name_txt
	if len(servings) > 0 and serving_text != "-1":
		entry.servings = float(serving_text)
	entry.PrepTimeSeconds = int(time_text)
	entry.ingredient_lines = ingredient_text
	entry.cooking_directions = direction_text
	if len(nutrients) > 0:
		entry.nutrients = nutrient_text
	entry.save()
	print "SAVED: ", entry.name, "-", status

		
# Search from the end of the string for the first "/".  Take a substring
# of the url from that found index.	
def extract_text_for_source_id(url):
	if sys.flags.debug:
		assert(url.rfind("/") != -1)
	return url[url.rfind("/") + 1:]

# Based on soup parsing name is soley an h1 tag.
def extract_text_for_name(name):
	if sys.flags.debug:
		assert(name[0].string != None)
	return name[0].string

# soup gives us li tags which may contain subtags.  Uses recursion to extract
# all strings from initial tag and any possible subtags.
def extract_text_for_ingredients(ingredients):
	new_list = []
	for i in ingredients:
		if i.string != None:
			new_list.append(i.string)
		else:
			string_pieces = []
			recursively_extract_text(i, string_pieces)
			
			if sys.flags.debug:
				print "RECURSION_STRING_PIECES: ", string_pieces
				
			concatonated_str = ""
			for piece in string_pieces:
				concatonated_str = concatonated_str + piece
			new_list.append(concatonated_str)
	return new_list

def recursively_extract_text(i, array):
	for child in i.children:
		if child.string != None:
			array.append(child.string)
		else:
			recursively_extract_text(child)

# soup returns us a div with p tags inside of it.  This method extracts the
# strings from the p tags while excluding '\n' and empty p tags.	
def extract_text_for_directions(directions):	
	new_list = []
	for child in directions[0].children:
		if not(child == '\n' or child.string == None):
			new_list.append(child.string)
	return new_list

# This extraction pulls a number out of the time tag text if it
# can find one.  If a number is found in the text, we attempt to
# determine the units of that time.  The default assumption is seconds.
def extract_text_for_time(time):

	start_index_of_PT_marker = time[0]['datetime'].find("PT")
	answer = time[0]['datetime'][start_index_of_PT_marker + 2: -1]

	if sys.flags.debug:
		assert(start_index_of_PT_marker != -1)
		assert(answer.isdigit())
		assert(time[0]['datetime'][-1].lower() == "h" or time[0]['datetime'][-1].lower() == "m" or time[0]['datetime'][-1].lower() == "d")
		print "FULL_TIME_TEXT: ", time[0]['datetime']
	
	if time[0]['datetime'][-1].lower() == "d":
		answer = str(int(answer) * 60 * 60 * 24)
	elif time[0]['datetime'][-1].lower() == "h":
		answer = str(int(answer) * 60 * 60)
	elif time[0]['datetime'][-1].lower() == "m":
		answer = str(int(answer) * 60)

	if sys.flags.debug:
		print "NUMS_TIME_TEXT: ", answer
	return answer

def extract_non_neg_ints(s):
	array = []
	for token in s.split():
		try:
			int(token)
			array.append(token)
		except ValueError:
			pass
	return array

def extract_non_neg_floats(s):		
	array = []
	for token in s.split():
		try:
			float(token)
			array.append(token)
		except ValueError:
			pass
	return array

# This method pulls all floats from servings text.  If exactly
# one number is found, it returns that as the serving.  If more
# than one number is found, it returns the largest serving.
def extract_text_for_servings(servings):
	nums_from_servings = []
	if servings[0].string == None:
		nums_from_servings = extract_non_neg_floats(servings[0].contents[0])
	else:	
		nums_from_servings = extract_non_neg_floats(servings[0].string)
	answer = "No numbers found in string."
	
	if sys.flags.debug:
		print "NUMS_SERVING_TEXT: ", nums_from_servings
		#assert(nums_from_servings.__len__() > 0)
		
	if nums_from_servings.__len__() > 0:
		if nums_from_servings.__len__() == 1:
			answer = nums_from_servings[0]
		else:
			if sys.flags.debug:
				print "FINDING LARGEST NUMBER"
				
			#finds the largest number from all numbers mentioned
			#in servings text	
			answer = "-1";
			for num in nums_from_servings:
				if float(num) > float(answer):
					answer = num
	else:
		#can't retrieve serving information
		answer = "-1"
	return answer

# Creates a dictionary from nutrients.  It uses the string outside 
# of the inner span tag as the key.  The value is a list that contains
# the amount of the nutrient at index 0 and the unit for that amount
# at index 1.  Based on the assumption that 
def extract_text_for_nutrients(nutrients):
	dictionary = {}
	for item in nutrients:
		nutrient = filter(remove_returns, item.contents)
		key = nutrient[0].string.strip()
		if sys.flags.debug:
			print "KEY_NUTRIENT_TEXT: ", key
		value = []	
		for token in nutrient[1].string.split():
			value.append(token)
			if token == "%" or token.lower() == "percent":
				#need to ask Laura what conversion technique I should use
				break
		if sys.flags.debug:
			print "VALUE_NUTRIENT_TEXT: ", value
		dictionary[key] = value
	return dictionary	
			
def remove_returns(str):
	return str != "\n"			
		
if __name__ == "__main__":
	if sys.flags.debug:
		print "Debug flag is ON"

	mongohelpers.drop_active_collection('cookstr_entry')
	mongohelpers.import_zazu_collection('cookstr_entry')
	full_scrape()
	mongohelpers.save_zazu_database('cookstr_entry','cookstr_entry.json')
	#page_scrape(base_url + empty_search_url, Queue.Queue())
	#scrape_url("http://www.cookstr.com/recipes/spicy-hot-chicken-soup")
	