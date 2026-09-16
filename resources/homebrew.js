let catalog = []
let filtered_catalog = []
const pageSize = 30;
let currentPage = 1;

function createHomebrewTiles() {
  const homebrew_list = document.getElementById("homebrew_list");
  homebrew_list.innerHTML = '';
  for(let i = 0; i < filtered_catalog.length; i++) {
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

fetch('catalog.json')
  .then(response => response.json())
  .then(data => {
    for (let i = 0; i < data.apps.length; i++) {
      catalog.push(data.apps[i]);
      if (i < pageSize) {
        filtered_catalog.push(data.apps[i]);
      }
    }
    createHomebrewTiles();
  })
  .catch(error => console.error('Error:', error));
