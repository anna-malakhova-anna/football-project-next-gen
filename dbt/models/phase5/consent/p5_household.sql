-- RESTRICTED. A household is a set of parent emails joined by the children they share: one parent email shared by siblings is one household; a family that used two
-- parent emails for the same child is also one household (the two emails are linked through the child). Connected components over emails (macro connected_components).
-- Children and records with no usable email belong to no household: they cannot be contacted, and the funnel counts them as such.
with person_emails as (

    select distinct p5_person_id, contact_email from {{ ref('p5_record_person') }} where contact_email is not null

),

nodes as (select distinct contact_email as node from person_emails),

edges as (

    select a.contact_email as a, b.contact_email as b
    from person_emails a join person_emails b on a.p5_person_id = b.p5_person_id and a.contact_email < b.contact_email

)

select node as contact_email, 'HH-' || md5(cluster_id) as household_id
from {{ connected_components('nodes', 'edges', []) }}
