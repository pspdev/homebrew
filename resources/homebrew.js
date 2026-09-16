let catalog = []
let filtered_catalog = []
const pageSize = 30;
let currentPage = 1;

function createHomebrewTiles() {
  const homebrew_list = document.getElementById("homebrew_list");
  homebrew_list.innerHTML = '';
  let starting_i = (currentPage - 1) * pageSize;
  for(let i = starting_i; i < filtered_catalog.length && i < starting_i + pageSize; i++) {
    let homebrew = document.createElement("div");
    homebrew.className = "homebrew";

    let name = document.createElement("div");
    name.className = "name";
    name.textContent = filtered_catalog[i].name;
    homebrew.appendChild(name);

    let icon_div = document.createElement("div");
    icon_div.className = "icon";
    let icon_img = document.createElement("img");
    icon_img.src = filtered_catalog[i].media.icon;
    icon_img.alt = "Icon";
    icon_div.appendChild(icon_img);
    homebrew.appendChild(icon_div);

    let summary = document.createElement("div");
    summary.className = "summary";
    summary.textContent = filtered_catalog[i].summary;
    homebrew.appendChild(summary);

    let tags_div = document.createElement("div");
    tags_div.className = "tags";
    for (let tag of filtered_catalog[i].tags) {
      let tag_div = document.createElement("div");
      tag_div.className = "tag";
      tag_div.textContent = tag;
      tags_div.appendChild(tag_div);
    }
    homebrew.appendChild(tags_div);

    let link = document.createElement("a");
    link.href = filtered_catalog[i].id + ".html";
    link.appendChild(homebrew);
    homebrew_list.appendChild(link);
  }
}

function changePage(page) {
  currentPage = page;
  scroll(0,0);
  createHomebrewTiles();
  createPaginationLinks();
}

function createPaginationLinks() {
  const pagination = document.getElementById("pagination");
  pagination.innerHTML = "";
  let pageCount = Math.ceil(filtered_catalog.length/pageSize);

  let first_div = document.createElement("div");
  let previous_div = document.createElement("div");
  if (currentPage > 1) {
    let first = document.createElement("a");
    first.innerHTML = "<< First";
    first.onclick = function() {
      changePage(1);
    };
    first.href="javascript:void(0);";
    first_div.appendChild(first)

    let previous = document.createElement("a");
    previous.innerHTML = "< Previous";
    previous.onclick = function() {
      changePage(currentPage - 1);
    };
    previous.href="javascript:void(0);";
    previous_div.appendChild(previous)
  }
  pagination.appendChild(first_div);
  pagination.appendChild(previous_div);


  let current_page_element = document.createElement("div");
  current_page_element.innerHTML = currentPage;
  pagination.appendChild(current_page_element);

  let next_div = document.createElement("div");
  let last_div = document.createElement("div");
  if (currentPage < pageCount) {
    let next = document.createElement("a");
    next.innerHTML = "Next >";
    next.onclick = function() {
      changePage(currentPage + 1);
    };
    next.href="javascript:void(0);";
    next_div.appendChild(next)

    let last = document.createElement("a");
    last.innerHTML = "Last >>";
    last.onclick = function() {
      changePage(pageCount);
    };
    last.href="javascript:void(0);";
    last_div.appendChild(last)
  }
  pagination.appendChild(next_div);
  pagination.appendChild(last_div);
}

function applyFilters() {
  let search = document.getElementById("search").value;
  let tag = document.getElementById("tag_select").value;
  let category = document.getElementById("category_select").value;

  filtered_catalog = []
  for (let i = 0; i < catalog.length; i++) {
    if (category.length > 0) {
      if (catalog[i].category != category) {
        continue;
      }
    }
    if (search.length > 0) {
      // If a search string is set and it doesn't match anything, skip this entry
      if (
        !catalog[i]["name"].toLowerCase().includes(search.toLowerCase()) &&
        !catalog[i]["summary"].toLowerCase().includes(search.toLowerCase()) &&
        !catalog[i]["author"].toLowerCase().includes(search.toLowerCase())
      ) {
        // Description is optional
        if (!catalog[i]["description"] || !catalog[i]["description"].toLowerCase().includes(search.toLowerCase())) {
          continue;
        }
      }
    }
    if (tag.length > 0) {
      let found_tag = false;
      for (let tag_i = 0; tag_i < catalog[i].tags.length; tag_i++) {
        if (catalog[i].tags[tag_i] == tag) {
          found_tag = true;
          break;
        }
      }
      if (!found_tag) {
        continue;
      }
    }
    filtered_catalog.push(catalog[i]);
  }
  currentPage = 1;
  createHomebrewTiles();
  createPaginationLinks();
}

function populateCategories() {
    let categories = []
    for (let i = 0; i < catalog.length; i++) {
      if (!categories.includes(catalog[i].category)) {
        categories.push(catalog[i].category)
      }
    }

    categories.sort();

    let category_select = document.getElementById("category_select");
    for (let i = 0; i < categories.length; i++) {
      let option = document.createElement("option");
      option.value = categories[i];
      option.innerHTML = categories[i].charAt(0).toUpperCase() + categories[i].slice(1);
      category_select.appendChild(option);
    }
}

function populateTags() {
    let tags = []
    for (let i = 0; i < catalog.length; i++) {
      for (let j = 0; j < catalog[i].tags.length; j++) {
        if (!tags.includes(catalog[i].tags[j])) {
          tags.push(catalog[i].tags[j])
        }
      }
    }

    tags.sort();

    let tag_select = document.getElementById("tag_select");
    for (let i = 0; i < tags.length; i++) {
      let option = document.createElement("option");
      option.value = tags[i];
      option.innerHTML = tags[i].charAt(0).toUpperCase() + tags[i].slice(1);
      tag_select.appendChild(option);
    }
}

fetch('catalog.json')
  .then(response => response.json())
  .then(data => {
    for (let i = 0; i < data.apps.length; i++) {
      catalog.push(data.apps[i]);
      filtered_catalog.push(data.apps[i]);
    }
    populateCategories();
    populateTags();
    createHomebrewTiles();
    createPaginationLinks();
  })
  .catch(error => console.error('Error:', error));
