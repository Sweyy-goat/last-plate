const foodList = document.getElementById("foodList");

if (foodList) {
  fetch("/api/foods")
    .then(res => res.json())
    .then(data => {
      foodList.innerHTML = ""; // clear old content

      data.foods.forEach(food => {
        const foodId = food[0];

        foodList.innerHTML += `
          <div style="border:1px solid #ccc; margin:10px; padding:10px">
            <h3>${food[1]}</h3>
            <p><strong>Restaurant:</strong> ${food[6]}</p>
            <p><strong>Price:</strong> ₹${food[2]}</p>
            <p><strong>Available:</strong> ${food[3]}</p>
            <p><strong>Pickup:</strong> ${food[4]} - ${food[5]}</p>

            <a href="/checkout/${foodId}">
              <button>Buy</button>
            </a>
          </div>
        `;
      });
    })
    .catch(err => {
      console.error("Failed to load foods:", err);
    });
  function formatTimeLeft(minutes) {
    if (minutes <= 0) return "Closed";

    if (minutes < 60) {
        return `⏳ Closing in ${minutes} min`;
    }

    const hrs = Math.floor(minutes / 60);
    const mins = minutes % 60;

    return mins === 0
        ? `⏳ Closing in ${hrs} hr`
        : `⏳ Closing in ${hrs} hr ${mins} min`;
}

}

