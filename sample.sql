with jt1 as ( 
  select 
    * 
  from 
    table1 t 
  where 
    a > 100 
      and b between 12 and 45
), 

jt2 as ( 
  select 
    * 
  from 
    ( 
      select 
        a, 
        b, 
        case 
          when c = 'some_value' 
              then x 
          else null 
        end as x, 
        case d 
          when 'another_value' then y 
          else null 
          end as y 
      from table2 
      where a > 100 
        and b between 12 and 45
) as subquery where c = 'some_value')

select 
  t.*, 
  j1.x, 
  j2.y 
from 
  table1 as t 
  join 
    jt1 as j1 
      on j1.a = t.a 
  left outer join 
    jt2 as j2 
      on j2.a = t.a 
      and j2.b = j1.b 
where 
  t.xxx is not null; 

delete 
from 
  table1 
where a = 1; 

update table1 
set 
  a = 2 
where 
  a = 1;

select 
  table1.id, 
  table2.number, 
  sum(table1.amount) 
from 
  table1 
    inner join table2 
      on table1.id = table2.table1_id 
where 
  table1.id in ( 
    select 
      table1_id 
    from 
      table3 
    where 
      table3.name = 'foo bar' 
        and table3.type = 'unknown_type'
  ) 
group by 
  table1.id, 
  table2.number 
order by 
  table1.id;