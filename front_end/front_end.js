const express = require('express');
const app = express();
const port = 3000;
const api = 8000;

app.set('view engine', 'ejs');
app.use(express.static('public'));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

app.get('/', (req, res) => {
    res.render('home');
});

app.get('/items', (req, res) => {
    let url = `http://localhost:${api}/items`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            let model = {itemList: data};
            console.log(model);
            res.render('items', model);
    });
});

app.get('/create-item', (req, res) => {
    res.render('edit-item', { isEdit: false });
});

app.post('/create-item', (req, res) => {
    let model = {name: req.body.name, description: req.body.description};

    let url = `http://localhost:${api}/new-item`;
    let headers = {
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        body: JSON.stringify(model),
        method: "POST"
    };
    fetch(url, headers)
        .then(response => response.json())
        .then(data => {
            console.log("Item added with ID: " + data.id);
            res.redirect('/items');
        });
});

app.get('/edit-item/:id', (req, res) => {
    const itemId = req.params.id;
    let url = `http://localhost:${api}/item/${itemId}`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            res.render('edit-item', { isEdit: true, item: data });
        });
});

app.post('/edit-item/:id', (req, res) => {
    const itemId = req.params.id;
    let model = {name: req.body.name, description: req.body.description};

    let url = `http://localhost:${api}/update-item/${itemId}`;
    let headers = {
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        body: JSON.stringify(model),
        method: "PUT"
    };
    fetch(url, headers)
        .then(response => response.json())
        .then(data => {
            console.log("Item updated with ID: " + data.id);
            res.redirect('/items');
        });
});

app.listen(port, () => {
    console.log(`Express is running on http://localhost:${port}/`);
});