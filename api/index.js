const {BigQuery} = require('@google-cloud/bigquery');
const bigquery = new BigQuery();
const functions = require('@google-cloud/functions-framework');

const handle_monthlyTimeSeries = async (req, res) => {

    // Year Begin
    const rawYearBegin =
      req.query?.year_begin ??
      req.body?.year_begin ??
      req.params?.year_begin;
    if (rawYearBegin === undefined) {
      return res.status(400).send('Missing required parameter: year_begin');
    }
    const req_YearBegin = Number.parseInt(String(rawYearBegin), 10);
    if (!Number.isFinite(req_YearBegin)) {
      return res.status(400).send('invalid year_begin');
    };

    // Year End
    const rawYearEnd =
      req.query?.year_end ??
      req.body?.year_end ??
      req.params?.year_end;
    if (rawYearEnd === undefined) {
      return res.status(400).send('Missing required parameter: year_end');
    }
    const req_YearEnd = Number.parseInt(String(rawYearEnd), 10);
    if (!Number.isFinite(req_YearEnd)) {
      return res.status(400).send('invalid year_end');
    };


    const sqlQuery = `
        SELECT * FROM \`bq-hackathon-hk.bq_dataset.bq_table_cluster_shares_monthly\` 
        where year >= @year_begin and year <= @year_end
        LIMIT 1000`;

    const options = {
        query: sqlQuery,
        location: 'europe-west4',
        params: {year_begin: req_YearBegin, year_end:req_YearEnd},
    };

  // Execute the query
    try {
        const [rows] = await bigquery.query(options);
        // Send the results
        return res.status(200).send(rows);
    } catch (err) {
        console.error(err);
        return res.status(500).send(`Error querying BigQuery: ${err}`);
    }


}

const handle_questionsByCluster = async (req, res) => {
     // 1) Parameter aus Query, Body oder (falls verwendet) Pfad lesen
    const rawCentroid =
      req.query?.centroid_id ??
      req.body?.centroid_id ??
      req.params?.centroid_id;

    if (rawCentroid === undefined) {
      return res.status(400).send('Missing required parameter: centroid_id');
    }

    // 2) In Zahl umwandeln und prüfen
    const req_centroid_id = Number.parseInt(String(rawCentroid), 10);
    if (!Number.isFinite(req_centroid_id)) {
      return res.status(400).send('invalid centroid_id');
    };
    

    const sqlQuery = `
        SELECT
        t1.question_summary,
        t1.url,
        t2.label
        FROM
        \`bq-hackathon-hk.bq_dataset.bq_table_cluster\` AS t1
        INNER JOIN
        \`bq-hackathon-hk.bq_dataset.bq_table_cluster_labels\` AS t2
        ON
        t1.CENTROID_ID = t2.CENTROID_ID
        where t1.centroid_id = @centroid_id and t2.rank = 1
        LIMIT 100`;

    const options = {
        query: sqlQuery,
        location: 'europe-west4',
        params: {centroid_id: req_centroid_id},
    };

  // Execute the query
    try {
        const [rows] = await bigquery.query(options);
        // Send the results
        return res.status(200).send(rows);
    } catch (err) {
        console.error(err);
        return res.status(500).send(`Error querying BigQuery: ${err}`);
    }
}

const handle_cluster = async (req, res) =>{
    const sqlQuery = `
        SELECT
        t1.label,
        t1.CENTROID_ID,
        t2.count_of_records
        FROM
        \`bq-hackathon-hk.bq_dataset.bq_table_cluster_labels\` AS t1
        INNER JOIN (
        SELECT
            CENTROID_ID,
            COUNT(CENTROID_ID) AS count_of_records
        FROM
            \`bq-hackathon-hk.bq_dataset.bq_table_cluster\`
        GROUP BY
            CENTROID_ID ) AS t2
        ON
        t1.CENTROID_ID = t2.CENTROID_ID
        WHERE
        t1.rank = 1
        LIMIT
        100;        
    `;

    const options = {
        query: sqlQuery,
        location: 'europe-west4',
    };

  // Execute the query
    try {
        const [rows] = await bigquery.query(options);
        // Send the results
        return res.status(200).send(rows);
    } catch (err) {
        console.error(err);
        return res.status(500).send(`Error querying BigQuery: ${err}`);
    }

}

const handle_yearRange = async (req, res) =>{
    const sqlQuery = `
        SELECT max(year) as max_year,
            min(year) as min_year
        FROM \`bq-hackathon-hk.bq_dataset.bq_table_cluster_shares_monthly\`    
    `;

    const options = {
        query: sqlQuery,
        location: 'europe-west4',
    };

  // Execute the query
    try {
        const [rows] = await bigquery.query(options);
        // Send the results
        return res.status(200).send(rows);
    } catch (err) {
        console.error(err);
        return res.status(500).send(`Error querying BigQuery: ${err}`);
    }
}



const handle_search = async (req, res) => {

    // 1) Parameter aus Query, Body oder (falls verwendet) Pfad lesen
    const rawQueryStr =
      req.query?.query ??
      req.body?.query ??
      req.params?.query;

    if (rawQueryStr === undefined) {
      return res.status(400).send('Missing required parameter: query');
    }

    // 2) In Zahl umwandeln und prüfen
    const req_queryStr = String(rawQueryStr);
    if (req_queryStr === undefined) {
      return res.status(400).send('invalid query');
    }

    const sqlQuery = `
        WITH q AS (
        SELECT @query_str AS content
        ),
        query_vec AS (
        SELECT ml_generate_embedding_result as query_embedding
        FROM ML.GENERATE_EMBEDDING(
            MODEL \`bq-hackathon-hk.bq_dataset.embedding_model\`,
            TABLE q,
            STRUCT('RETRIEVAL_QUERY' AS task_type)
        )
        )
        SELECT distance,
            base.question_summary,
            base.url,
            base.CENTROID_ID
        FROM VECTOR_SEARCH(
            TABLE \`bq-hackathon-hk.bq_dataset.bq_table_cluster\`,
            'embeddings',
            (SELECT query_embedding FROM query_vec),
            top_k => 10,
            distance_type => 'COSINE'
            )ORDER BY distance ASC;
    `;

    const options = {
        query: sqlQuery,
        location: 'europe-west4',
        params: {query_str: req_queryStr},
    };

  // Execute the query
    try {
        const [rows] = await bigquery.query(options);
        // Send the results
        return res.status(200).send(rows);
    } catch (err) {
        console.error(err);
        return res.status(500).send(`Error querying BigQuery: ${err}`);
    }
}

functions.http('main', async (req, res) => {
  // https://cloud.google.com/run/docs/write-http-functions#node.js
    console.log(req.path);
    res.set('Access-Control-Allow-Origin', '*');
    if (req.method === 'OPTIONS') {
        // Send response to OPTIONS requests
        res.set('Access-Control-Allow-Methods', 'GET');
        res.set('Access-Control-Allow-Headers', 'Content-Type');
        res.set('Access-Control-Max-Age', '3600');
        return res.status(204).send('');
    }  

    // routing
    if (req.path == "/monthlyTimeSeries" )
        return handle_monthlyTimeSeries(req, res);

    if (req.path == "/questionsByCluster" )
        return handle_questionsByCluster(req, res);

    if (req.path == "/cluster" )
        return handle_cluster(req, res);

    if (req.path == "/search" )
        return handle_search(req, res);

    if (req.path == "/yearRange" )
        return handle_yearRange(req, res);


    return res.status(400).send('invalid path');
});


